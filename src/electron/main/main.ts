import { join } from 'path';
import {
    app,
    BrowserWindow,
    ipcMain,
    dialog
} from 'electron';

const isDev = process.env.npm_lifecycle_event === "app:dev" ? true : false;

async function handleFileOpen() {
    const { canceled, filePaths } = await dialog.showOpenDialog({ title: "Open File" })
    if (!canceled) {
        return filePaths[0]
    }
}

function createWindow() {
    const mainWindow = new BrowserWindow({
        width: 850,
        height: 500,
        minWidth: 850,
        minHeight: 500,
        frame: true,
        autoHideMenuBar: true,
        title: 'AIMakeup 美妆镜',
        icon: isDev ? join(__dirname, '../../public/favicon.ico') : join(__dirname, '../../favicon.ico'),
        webPreferences: {
            preload: join(__dirname, '../preload/preload.js'),
            webSecurity: false, // 允许跨域访问本地后端
        },
    });

    if (isDev) {
        mainWindow.loadURL('http://localhost:3000');
        mainWindow.webContents.openDevTools();
    } else {
        mainWindow.loadFile(join(__dirname, '../../index.html'));
    }
}

app.whenReady().then(() => {
    ipcMain.handle('dialog:openFile', handleFileOpen)
    createWindow()
    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
});

app.on('window-all-closed', () => {
    if (process.platform !== 'win32') {
        app.quit();
    }
});
