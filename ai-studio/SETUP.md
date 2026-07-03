# AI Studio — Setup Guide

## Requirements
- Windows 10/11
- Node.js 18+ (https://nodejs.org)
- ComfyUI installed locally
- Your model files placed in ComfyUI's `models/checkpoints/` folder

## 1. Install Node dependencies
```
cd ai-studio
npm install
```

## 2. Place your model files
Copy your `.safetensors` files into ComfyUI's checkpoint folder:
```
C:\ComfyUI\models\checkpoints\
```
The filenames must match what's in `config/image-presets.json` and `config/video-presets.json`.

For example:
- `lustify_sdxl.safetensors`
- `lustify_v8.safetensors`
- `wai_anime.safetensors`
- `venice_sd35.safetensors`
- `wan27_uncensored.safetensors`
- etc.

## 3. Launch the app
```
npm start
```

The app will open a window titled **AI Studio**.  
If ComfyUI is not running, click **Launch** in the bottom-left corner.

## 4. Update model filenames
Edit `config/image-presets.json` and `config/video-presets.json` to match
your exact filenames if they differ from the defaults.

## Output location
All generated images and videos are saved to:
```
C:\Users\<you>\Pictures\AI-Studio\<date>\<model-id>\
```
