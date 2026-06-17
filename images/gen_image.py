import requests
import uuid

class ImageGenerator:
    def __init__(self, api_url="http://192.168.40.236:9090"):
        self.api_url = api_url

    def generate_image(self, prompt: str):
        batch_id = str(uuid.uuid4())

        payload = {
            "batch": {
                "id": batch_id,
                "type": "invoke_workflow",
                "graph": {
                    "id": batch_id,
                    "nodes": {
                        "load_model": {
                            "id": "load_model",
                            "type": "sdxl_model_loader",
                            "model": {
                                "base": "sdxl",
                                "type": "main",
                                "name": "Deliberate_v6",
                                "variant": "fp16",
                                "format": "diffusers",
                                "hash": "placeholder_hash",
                                "key": "Deliberate_v6"
                            },
                            "is_intermediate": True
                        },
                        "t2i": {
                            "id": "t2i",
                            "type": "t2i_adapter",
                            "prompt": prompt,
                            "steps": 30,
                            "cfg_scale": 7,
                            "width": 512,
                            "height": 512,
                            "scheduler": "dpmsolver",
                            "is_intermediate": False
                        }
                    },
                    "edges": [
                        {
                            "source": {"node_id": "load_model", "field": "unet"},
                            "destination": {"node_id": "t2i", "field": "unet"}
                        },
                        {
                            "source": {"node_id": "load_model", "field": "clip"},
                            "destination": {"node_id": "t2i", "field": "clip"}
                        }
                    ]
                },
                "workflow": {
                    "name": "Text to Image Generation",
                    "author": "LocalUser",
                    "description": "Simple image generation workflow",
                    "version": "1.0.0",
                    "contact": "user@local.ai",
                    "tags": "image, text2img",
                    "notes": "Generated via CLI integration",
                    "exposedFields": [],
                    "meta": {
                        "version": "1.0.0",
                        "category": "user"
                    },
                    "nodes": [
                        {
                            "id": "load_model",
                            "type": "sdxl_model_loader",
                            "model": {
                                "base": "sdxl",
                                "type": "main",
                                "name": "Deliberate_v6",
                                "variant": "fp16",
                                "format": "diffusers",
                                "hash": "placeholder_hash",
                                "key": "Deliberate_v6"
                            }
                        },
                        {
                            "id": "t2i",
                            "type": "t2i_adapter",
                            "prompt": prompt,
                            "steps": 30,
                            "cfg_scale": 7,
                            "width": 512,
                            "height": 512,
                            "scheduler": "dpmsolver"
                        }
                    ],
                    "edges": [
                        {
                            "source": {"node_id": "load_model", "field": "unet"},
                            "destination": {"node_id": "t2i", "field": "unet"}
                        },
                        {
                            "source": {"node_id": "load_model", "field": "clip"},
                            "destination": {"node_id": "t2i", "field": "clip"}
                        }
                    ],
                    "form": {}
                }
            },
            "prepend": False,
            "validation_run_data": {
                "workflow_id": batch_id,
                "input_fields": [],
                "output_fields": []
            }
        }

        response = requests.post(
            f"{self.api_url}/api/v1/queue/default/enqueue_batch",
            json=payload
        )

        print("[ImageGen] Response Code:", response.status_code)
        try:
            print("[ImageGen] Response:", response.json())
        except Exception:
            print("[ImageGen] Raw Response:", response.text)
