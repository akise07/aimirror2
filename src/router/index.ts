import { createWebHashHistory, createRouter } from "vue-router";
import CameraView from "../components/CameraView.vue";
import MakeupGen from "../components/MakeupGen.vue";
import VideoGen from "../components/VideoGen.vue";
import RecommendView from "../components/RecommendView.vue";
import SettingsView from "../components/SettingsView.vue";

const routes = [
  {
    path: "/",
    redirect: "/camera",
  },
  {
    path: "/camera",
    name: "Camera",
    component: CameraView,
  },
  {
    path: "/makeup",
    name: "Makeup",
    component: MakeupGen,
  },
  {
    path: "/video",
    name: "Video",
    component: VideoGen,
  },
  {
    path: "/recommend",
    name: "Recommend",
    component: RecommendView,
  },
  {
    path: "/settings",
    name: "Settings",
    component: SettingsView,
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
