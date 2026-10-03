"""Image -> 3D shape with the local ComfyUI (Hunyuan3D v2). Usage: python comfy_hunyuan3d.py <input image name in ComfyUI/input> <output prefix> [seed] [octree]"""
import json, sys, time, urllib.request

HOST = "http://127.0.0.1:8195"
img = sys.argv[1]
prefix = sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
octree = int(sys.argv[4]) if len(sys.argv) > 4 else 384

wf = {
    "1": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {"ckpt_name": "hunyuan3d-dit-v2_fp16.safetensors"}},
    "2": {"class_type": "LoadImage", "inputs": {"image": img}},
    "3": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["1", 1], "image": ["2", 0], "crop": "center"}},
    "4": {"class_type": "Hunyuan3Dv2Conditioning", "inputs": {"clip_vision_output": ["3", 0]}},
    "5": {"class_type": "EmptyLatentHunyuan3Dv2", "inputs": {"resolution": 3072, "batch_size": 1}},
    "6": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 1.0}},
    "7": {"class_type": "KSampler", "inputs": {"model": ["6", 0], "seed": seed, "steps": 40, "cfg": 5.0, "sampler_name": "euler", "scheduler": "normal",
                                               "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["5", 0], "denoise": 1.0}},
    "8": {"class_type": "VAEDecodeHunyuan3D", "inputs": {"samples": ["7", 0], "vae": ["1", 2], "num_chunks": 8000, "octree_resolution": octree}},
    "9": {"class_type": "VoxelToMesh", "inputs": {"voxel": ["8", 0], "algorithm": "surface net", "threshold": 0.6}},
    "10": {"class_type": "SaveGLB", "inputs": {"mesh": ["9", 0], "filename_prefix": prefix}},
}
req = urllib.request.Request(HOST + "/prompt", data=json.dumps({"prompt": wf}).encode(), headers={"Content-Type": "application/json"})
try:
    resp = json.load(urllib.request.urlopen(req, timeout=30))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:2000]); sys.exit(1)
pid = resp["prompt_id"]
print("queued", pid)
t0 = time.time()
while time.time() - t0 < 1500:
    h = json.load(urllib.request.urlopen(HOST + "/history/" + pid, timeout=30))
    if pid in h:
        e = h[pid]
        print("status", e.get("status", {}).get("status_str"))
        print(json.dumps(e.get("outputs"), indent=1)[:1500])
        for m in e.get("status", {}).get("messages", []):
            if m[0] == "execution_error":
                print("ERROR", json.dumps(m[1])[:2500])
        break
    time.sleep(5)
print("elapsed", round(time.time() - t0))
