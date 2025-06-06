import timm
import torch

import os
import zipfile
import torch
import timm

AVAILABLE_MODELS = {
    "Swin": "../models/ad_classifier_swin.pth"
}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PRELOADED_MODELS = {}

def extract_model_if_needed(zip_path, extract_to):
    if not os.path.exists(extract_to):
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.dirname(extract_to))

def load_model(model_name):
    if model_name in PRELOADED_MODELS:
        return PRELOADED_MODELS[model_name]

    model_path = AVAILABLE_MODELS.get(model_name)

    zip_path = model_path.replace('.pth', '.zip')
    if os.path.exists(zip_path):
        extract_model_if_needed(zip_path, '../ad_classifier_swin.pth')

    model = timm.create_model("swin_tiny_patch4_window7_224", pretrained=True, num_classes=2)
    if model_path and model is not None:
        try:
            model.load_state_dict(torch.load(model_path, map_location=device))
            model.to(device)
            model.eval()
        except Exception as e:
            print(f"Ошибка загрузки модели {model_name}: {e}")
            return None
    else:
        print(f"Ошибка: модель {model_name} не найдена в AVAILABLE_MODELS.")
        return None

    PRELOADED_MODELS[model_name] = model
    return model


def preload_all_models():
    for model_name in AVAILABLE_MODELS.keys():
        model = load_model(model_name)
        if model is not None:
            print(f"Модель {model_name} успешно загружена.")
        else:
            print(f"Не удалось загрузить модель {model_name}.")
