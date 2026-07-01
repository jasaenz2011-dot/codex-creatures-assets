Reserved for the embedded, headless ComfyUI instance used for complex video
workflows. Add it as a git submodule (`git submodule add <comfyui-repo> vendor/ComfyUI`)
and have the Python backend launch it with `--headless` on a fixed local port
(e.g. 8188) without opening a browser window. Not needed for direct-diffusers
image generation.
