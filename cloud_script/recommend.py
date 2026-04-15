import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from transformers import (
    CLIPVisionModel, CLIPImageProcessor,
    AutoTokenizer, AutoModelForCausalLM
)
from PIL import Image
import numpy as np
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import io



# ============================================================
# 1. 配置
# ============================================================
@dataclass
class ModelConfig:
    # ViT 配置 —— 本地 CLIP ViT-L/14
    vit_model_name: str = "/gemini/pretrain2/clip-vit-large-patch14"
    vit_embed_dim: int = 1024           # CLIP ViT-L/14 的 hidden_size

    # VAE 配置
    vae_input_dim: int = 3 * 224 * 224
    vae_hidden_dims: List[int] = field(default_factory=lambda: [1024, 512, 256])
    vae_latent_dim: int = 256

    # 特征融合配置
    fusion_dim: int = 512

    # LLM 配置 —— 本地 Qwen2.5-3B
    llm_model_name: str = "/gemini/pretrain/Qwen2.5-3B-Instruct"
    llm_max_length: int = 512

    # 妆容类别
    num_makeup_categories: int = 6
    num_skin_tones: int = 5

    # 输入图片
    image_path: str = "test.jpg"


# ============================================================
# 2. VAE 模块
# ============================================================
class MakeupVAE(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config

        # 编码器
        encoder_layers = []
        in_dim = config.vae_input_dim
        for h_dim in config.vae_hidden_dims:
            encoder_layers.extend([
                nn.Linear(in_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.LeakyReLU(0.2),
                nn.Dropout(0.1),
            ])
            in_dim = h_dim
        self.encoder = nn.Sequential(*encoder_layers)

        self.fc_mu = nn.Linear(config.vae_hidden_dims[-1], config.vae_latent_dim)
        self.fc_logvar = nn.Linear(config.vae_hidden_dims[-1], config.vae_latent_dim)

        # 解码器
        decoder_layers = []
        decoder_dims = list(reversed(config.vae_hidden_dims))
        in_dim = config.vae_latent_dim
        for h_dim in decoder_dims:
            decoder_layers.extend([
                nn.Linear(in_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.LeakyReLU(0.2),
            ])
            in_dim = h_dim
        decoder_layers.append(nn.Linear(in_dim, config.vae_input_dim))
        decoder_layers.append(nn.Sigmoid())
        self.decoder = nn.Sequential(*decoder_layers)

    def encode(self, x):
        h = self.encoder(x)
        return self.fc_mu(h), self.fc_logvar(h)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        return mu + torch.randn_like(std) * std

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        return self.decode(z), mu, logvar

    @staticmethod
    def vae_loss(recon, original, mu, logvar, recon_weight=1.0, kl_weight=0.001):
        recon_loss = F.mse_loss(recon, original, reduction='sum')
        kl_loss = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
        return recon_weight * recon_loss + kl_weight * kl_loss


# ============================================================
# 3. ViT 特征提取器（CLIP ViT-L/14）
# ============================================================
class VitFeatureExtractor(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config

        self.vit = CLIPVisionModel.from_pretrained(config.vit_model_name)

        # ====== 修改：CLIPVisionModel 的层级结构不同 ======
        # 结构: CLIPVisionModel → vision_model → (embeddings, encoder, pre_layrnorm, post_layernorm)
        vision_model = self.vit.vision_model

        # 冻结 embeddings
        for param in vision_model.embeddings.parameters():
            param.requires_grad = False

        # 冻结 encoder 前 16 层（CLIP ViT-L 共 24 层）
        for layer in vision_model.encoder.layers[:16]:
            for param in layer.parameters():
                param.requires_grad = False

        # 冻结 pre_layrnorm
        for param in vision_model.pre_layrnorm.parameters():
            param.requires_grad = False
        # ====== 修改结束 ======

        # 投影：1024 → fusion_dim
        self.global_proj = nn.Sequential(
            nn.Linear(config.vit_embed_dim, config.fusion_dim),
            nn.LayerNorm(config.fusion_dim),
            nn.GELU(),
            nn.Dropout(0.1),
        )

        # Patch attention pooling
        self.patch_attention = nn.MultiheadAttention(
            embed_dim=config.vit_embed_dim, num_heads=8, batch_first=True
        )
        self.patch_proj = nn.Sequential(
            nn.Linear(config.vit_embed_dim, config.fusion_dim),
            nn.LayerNorm(config.fusion_dim),
            nn.GELU(),
        )

        # 辅助分类头
        self.makeup_classifier = nn.Sequential(
            nn.Linear(config.fusion_dim * 2, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
        )
        self.makeup_style_head = nn.Linear(256, config.num_makeup_categories)
        self.skin_tone_head = nn.Linear(256, config.num_skin_tones)

    def forward(self, pixel_values):
        outputs = self.vit(pixel_values=pixel_values)
        cls_token = outputs.last_hidden_state[:, 0, :]
        patch_tokens = outputs.last_hidden_state[:, 1:, :]

        global_feat = self.global_proj(cls_token)

        query = cls_token.unsqueeze(1)
        attn_out, _ = self.patch_attention(query, patch_tokens, patch_tokens)
        patch_feat = self.patch_proj(attn_out.squeeze(1))

        combined = torch.cat([global_feat, patch_feat], dim=-1)
        aux_hidden = self.makeup_classifier(combined)
        makeup_logits = self.makeup_style_head(aux_hidden)
        skin_logits = self.skin_tone_head(aux_hidden)

        return {
            "global_feat": global_feat,
            "patch_feat": patch_feat,
            "combined_feat": combined,
            "makeup_logits": makeup_logits,
            "skin_logits": skin_logits,
        }


# ============================================================
# 4. 特征融合模块
# ============================================================
class FeatureFusion(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config

        self.vae_proj = nn.Sequential(
            nn.Linear(config.vae_latent_dim, config.fusion_dim),
            nn.LayerNorm(config.fusion_dim),
            nn.GELU(),
        )

        self.cross_attn = nn.MultiheadAttention(
            embed_dim=config.fusion_dim, num_heads=8, batch_first=True
        )

        self.gate = nn.Sequential(
            nn.Linear(config.fusion_dim * 3, config.fusion_dim),
            nn.Sigmoid(),
        )

        # 投影到 LLM 嵌入空间（先投影到通用维度，再由 llm_adapter 匹配）
        self.to_llm_dim = nn.Sequential(
            nn.Linear(config.fusion_dim, config.fusion_dim),
            nn.GELU(),
            nn.Linear(config.fusion_dim, 2048),
            nn.LayerNorm(2048),
        )

        self.visual_tokens = nn.Parameter(
            torch.randn(1, 8, config.fusion_dim) * 0.02
        )

    def forward(self, vit_global, vit_patch, vae_latent):
        B = vit_global.size(0)

        vae_feat = self.vae_proj(vae_latent)
        vit_seq = torch.stack([vit_global, vit_patch], dim=1)
        vae_query = vae_feat.unsqueeze(1)
        attn_out, _ = self.cross_attn(vae_query, vit_seq, vit_seq)
        attn_feat = attn_out.squeeze(1)

        gate_input = torch.cat([vit_global, vit_patch, vae_feat], dim=-1)
        g = self.gate(gate_input)
        fused = g * attn_feat + (1 - g) * (vit_global + vae_feat) / 2

        visual_tokens = self.visual_tokens.expand(B, -1, -1)
        fused_expanded = fused.unsqueeze(1).expand(-1, 8, -1)
        visual_tokens = visual_tokens + fused_expanded

        return self.to_llm_dim(visual_tokens)


# ============================================================
# 5. 完整模型
# ============================================================
class MakeupRecommendationModel(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config

        self.vit_extractor = VitFeatureExtractor(config)
        self.vae = MakeupVAE(config)
        self.fusion = FeatureFusion(config)

        # 从本地路径加载 LLM
        print(f"加载 LLM: {config.llm_model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(config.llm_model_name)
        self.llm = AutoModelForCausalLM.from_pretrained(
            config.llm_model_name,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )

        # 冻结 LLM
        for param in self.llm.parameters():
            param.requires_grad = False

        # LLM 隐藏维度适配
        self.llm_hidden_size = self.llm.config.hidden_size
        print(f"LLM hidden_size: {self.llm_hidden_size}")

        if 2048 != self.llm_hidden_size:
            self.llm_adapter = nn.Linear(2048, self.llm_hidden_size)
        else:
            self.llm_adapter = nn.Identity()

    def encode_image(self, images, flattened_images):
        vit_out = self.vit_extractor(images)
        recon, mu, logvar = self.vae(flattened_images)
        return {
            "vit_global": vit_out["global_feat"],
            "vit_patch": vit_out["patch_feat"],
            "makeup_logits": vit_out["makeup_logits"],
            "skin_logits": vit_out["skin_logits"],
            "vae_recon": recon,
            "vae_mu": mu,
            "vae_logvar": logvar,
            "vae_latent": mu,
        }

    def generate_recommendation(self, images, flattened_images,
                             user_prompt="请根据我的面部特征，推荐适合我的妆容方案。",
                             max_new_tokens=256):
        self.eval()
        with torch.no_grad():
            encoded = self.encode_image(images, flattened_images)
    
            visual_embeds = self.fusion(
                encoded["vit_global"],
                encoded["vit_patch"],
                encoded["vae_latent"],
            )
            visual_embeds = self.llm_adapter(visual_embeds)
    
            # ★ 关键修复：将视觉嵌入转为与 LLM 相同的 dtype
            visual_embeds = visual_embeds.to(dtype=self.llm.dtype)
    
            # 辅助分析信息
            makeup_probs = F.softmax(encoded["makeup_logits"], dim=-1)
            skin_probs = F.softmax(encoded["skin_logits"], dim=-1)
            makeup_styles = ["日常淡妆", "职场通勤", "约会甜美", "派对烟熏", "复古港风", "清透裸妆"]
            skin_tones = ["冷白皮", "暖白皮", "自然肤色", "健康小麦色", "深肤色"]
            top_makeup = makeup_styles[makeup_probs.argmax().item()]
            top_skin = skin_tones[skin_probs.argmax().item()]
    
            system_msg = (
                "你是一位专业的美妆顾问。你将看到用户面部图像的视觉特征分析结果，"
                "请根据这些特征给出个性化的妆容推荐，包括底妆、眼妆、唇妆、修容等建议。"
                "请分析肤色、五官特点，并推荐具体的产品色号和化妆技巧。"
            )
            aux_info = (
                f"\n[视觉特征分析]\n"
                f"- 检测到最适合的妆容风格: {top_makeup}\n"
                f"- 检测到肤色类型: {top_skin}\n"
            )
            prompt = f"{system_msg}\n{aux_info}\n用户问题: {user_prompt}\n\n回答:"
    
            text_ids = self.tokenizer.encode(prompt, return_tensors="pt").to(images.device)
            text_embeds = self.llm.get_input_embeddings()(text_ids)
    
            # ★ 同时确保 text_embeds 也是相同 dtype
            text_embeds = text_embeds.to(dtype=self.llm.dtype)
    
            input_embeds = torch.cat([visual_embeds, text_embeds], dim=1)
    
            output = self.llm.generate(
                inputs_embeds=input_embeds,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                repetition_penalty=1.1,
            )
    
            response = self.tokenizer.decode(output[0], skip_special_tokens=True)
            return response


    def compute_loss(self, images, flattened_images, makeup_labels, skin_labels,
                     original_images_flat):
        encoded = self.encode_image(images, flattened_images)

        vae_loss = MakeupVAE.vae_loss(
            encoded["vae_recon"], original_images_flat,
            encoded["vae_mu"], encoded["vae_logvar"],
        )
        makeup_loss = F.cross_entropy(encoded["makeup_logits"], makeup_labels)
        skin_loss = F.cross_entropy(encoded["skin_logits"], skin_labels)

        total_loss = 0.1 * vae_loss + 0.3 * makeup_loss + 0.2 * skin_loss
        return {
            "total_loss": total_loss,
            "vae_loss": vae_loss,
            "makeup_loss": makeup_loss,
            "skin_loss": skin_loss,
        }


# ============================================================
# 6. 数据集
# ============================================================
class MakeupFaceDataset(Dataset):
    def __init__(self, image_paths, makeup_labels, skin_labels, image_size=224):
        self.image_paths = image_paths
        self.makeup_labels = makeup_labels
        self.skin_labels = skin_labels

        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.3),
            transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self.flat_transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
        ])

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        img = Image.open(self.image_paths[idx]).convert("RGB")
        return {
            "images": self.transform(img),
            "flattened_images": self.flat_transform(img).view(-1),
            "makeup_label": self.makeup_labels[idx],
            "skin_label": self.skin_labels[idx],
        }


# ============================================================
# 7. 训练器
# ============================================================
class MakeupTrainer:
    def __init__(self, config, device="cuda"):
        self.config = config
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.model = MakeupRecommendationModel(config).to(self.device)

        trainable_params = [p for p in self.model.parameters() if p.requires_grad]
        print(f"可训练参数量: {sum(p.numel() for p in trainable_params):,}")

        self.optimizer = torch.optim.AdamW(trainable_params, lr=1e-4, weight_decay=0.01)
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=50, eta_min=1e-6
        )

    def train_epoch(self, dataloader):
        self.model.train()
        epoch_losses = {"total": 0, "vae": 0, "makeup": 0, "skin": 0}

        for batch in dataloader:
            images = batch["images"].to(self.device)
            flattened = batch["flattened_images"].to(self.device)
            makeup_labels = batch["makeup_label"].to(self.device)
            skin_labels = batch["skin_label"].to(self.device)

            losses = self.model.compute_loss(
                images, flattened, makeup_labels, skin_labels, flattened
            )

            self.optimizer.zero_grad()
            losses["total_loss"].backward()
            torch.nn.utils.clip_grad_norm_(
                [p for p in self.model.parameters() if p.requires_grad], 1.0
            )
            self.optimizer.step()

            for k in epoch_losses:
                epoch_losses[k] += losses[f"{k}_loss" if k != "total" else "total_loss"].item()

        n = len(dataloader)
        return {k: v / n for k, v in epoch_losses.items()}

    def train(self, train_dataset, epochs=50, batch_size=16):
        dataloader = DataLoader(
            train_dataset, batch_size=batch_size,
            shuffle=True, num_workers=4, pin_memory=True
        )
        for epoch in range(1, epochs + 1):
            losses = self.train_epoch(dataloader)
            self.scheduler.step()
            print(f"Epoch {epoch}/{epochs} | "
                  f"Total: {losses['total']:.4f} | "
                  f"VAE: {losses['vae']:.4f} | "
                  f"Makeup: {losses['makeup']:.4f} | "
                  f"Skin: {losses['skin']:.4f}")

    def save_checkpoint(self, path):
        trainable_state = {
            k: v for k, v in self.model.state_dict().items()
            if not k.startswith("llm.")
        }
        torch.save({
            "config": self.config,
            "model_state": trainable_state,
            "optimizer_state": self.optimizer.state_dict(),
        }, path)


# ============================================================
# 8. 推理服务
# ============================================================
class MakeupRecommendationService:
    def __init__(self, checkpoint_path, config, device="cuda"):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.config = config

        self.model = MakeupRecommendationModel(config).to(self.device)
        if checkpoint_path and os.path.exists(checkpoint_path):
            ckpt = torch.load(checkpoint_path, map_location=self.device)
            self.model.load_state_dict(ckpt["model_state"], strict=False)
            print(f"已加载 checkpoint: {checkpoint_path}")
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self.flat_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
        ])

    @torch.no_grad()
    def recommend(self, image_path, user_prompt=None):
        img = Image.open(image_path).convert("RGB")
        vit_input = self.transform(img).unsqueeze(0).to(self.device)
        flat_input = self.flat_transform(img).view(1, -1).to(self.device)

        if user_prompt is None:
            user_prompt = "请根据我的面部特征，推荐适合我的妆容方案。"

        return self.model.generate_recommendation(vit_input, flat_input, user_prompt)


class RecommendGenerator:
    def __init__(self):
        self.step_status = {"step": 0, "msg": ""}
        # ========== 配置 ==========
        self.config = ModelConfig(
            vit_model_name="/gemini/pretrain2/clip-vit-large-patch14",
            llm_model_name="/gemini/pretrain/Qwen2.5-3B-Instruct",
            vae_latent_dim=256,
            fusion_dim=512,
            image_path="test.jpg",
        )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        print("=" * 60)
        print("妆容推荐系统")
        print(f"  ViT: {self.config.vit_model_name}")
        print(f"  LLM: {self.config.llm_model_name}")
        print(f"  图片: {self.config.image_path}")
        print(f"  设备: {self.device}")
        print("=" * 60)

    def makeup_recommend(self, image=None):
        # ========== 加载图片 ==========
        self.step_status = {"step": 0, "msg": "加载图片中"}
        
        # image_path = self.config.image_path
        # if not os.path.exists(image_path):
        #     raise FileNotFoundError(f"找不到图片: {image_path}")

        # img = Image.open(image_path).convert("RGB")
        img = Image.open(io.BytesIO(image)).convert("RGB")
        print(f"图片已加载: {img.size}")

        # ViT 预处理
        vit_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        flat_transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
        ])

        vit_input = vit_transform(img).unsqueeze(0).to(self.device)
        flat_input = flat_transform(img).view(1, -1).to(self.device)

        self.step_status = {"step": 10, "msg": "模型加载中"}

        # ========== 初始化模型 ==========
        print("\n正在加载模型...")
        model = MakeupRecommendationModel(self.config).to(self.device)
        model.eval()

        self.step_status = {"step": 30, "msg": "特征提取中"}

        # ========== 特征提取 ==========
        print("\n正在提取特征...")
        with torch.no_grad():
            encoded = model.encode_image(vit_input, flat_input)

        print(f"\n[特征维度]")
        print(f"  ViT 全局特征:    {encoded['vit_global'].shape}")
        print(f"  ViT Patch 特征:  {encoded['vit_patch'].shape}")
        print(f"  VAE 潜在向量:    {encoded['vae_latent'].shape}")
        print(f"  妆容分类 logits: {encoded['makeup_logits'].shape}")
        print(f"  肤色分类 logits: {encoded['skin_logits'].shape}")

        self.step_status = {"step": 50, "msg": "特征融合中"}

        # ========== 特征融合 ==========
        with torch.no_grad():
            visual_embeds = model.fusion(
                encoded["vit_global"],
                encoded["vit_patch"],
                encoded["vae_latent"],
            )
        print(f"  融合后视觉嵌入:  {visual_embeds.shape}")

        # ========== 模型统计 ==========
        total_params = sum(p.numel() for p in model.parameters())
        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"\n[模型统计]")
        print(f"  总参数量:     {total_params:,}")
        print(f"  可训练参数量: {trainable_params:,}")
        print(f"  冻结参数量:   {total_params - trainable_params:,}")

        self.step_status = {"step": 70, "msg": "生成妆容推荐中"}

        # ========== 生成妆容推荐 ==========
        print("\n" + "=" * 60)
        print("正在生成妆容推荐...")
        print("=" * 60)

        user_prompt = (
            "请根据我的面部特征，推荐适合我的妆容方案，"
            "包括底妆色号、眼影配色、唇色和修容建议。"
        )

        recommendation = model.generate_recommendation(
            images=vit_input,
            flattened_images=flat_input,
            user_prompt=user_prompt,
            max_new_tokens=300,
        )

        self.step_status = {"step": 100, "msg": "推荐结果已生成", "result": recommendation}

        print(f"\n{'=' * 60}")
        print("[妆容推荐结果]")
        print("=" * 60)
        print(recommendation)
