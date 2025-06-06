import cv2
import torch
import torchvision.transforms as transforms
from PIL import Image
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])


def classify_frame(frame, model):
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    image_tensor = transform(image).unsqueeze(0).to(device)
    with torch.no_grad():
        outputs = model(image_tensor)
        _, predicted = torch.max(outputs, 1)
    return predicted.item()


def process_video_segments(video_path, model, start_time, end_time, frame_interval=0.5):
    cap = cv2.VideoCapture(video_path)
    total_frames = 0
    ad_frames = 0
    frame_count = 0
    current_time = start_time
    while current_time <= end_time:
        cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1
        label = classify_frame(frame, model)

        if label == 0:
            ad_frames += 1

        current_time += frame_interval
        frame_count += 1

    cap.release()
    ad_percentage = (ad_frames / total_frames) * 100 if total_frames > 0 else 0.0
    return ad_percentage


# Вычисляем взвешенный процент рекламы
def process_video_segments_weigth(video_path, model, start_time, end_time, frame_interval=0.5):
    cap = cv2.VideoCapture(video_path)
    total_weighted_value = 0.0
    total_weight = 0.0
    current_time = start_time
    segment_duration = end_time - start_time
    while current_time <= end_time:
        cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
        ret, frame = cap.read()
        if not ret:
            break
        frame_position = (current_time - start_time) / segment_duration
        weight = frame_position

        label = classify_frame(frame, model)
        total_weight += weight
        if label == 0:
            total_weighted_value += weight

        current_time += frame_interval

    cap.release()
    weighted_ad_percentage = (total_weighted_value / total_weight) * 100 if total_weight > 0 else 0.0
    return weighted_ad_percentage

def process_video_segments_after_(video_path, model, start_time, end_time, frame_interval=0.5):
    cap = cv2.VideoCapture(video_path)
    total_frames = 0
    ad_frames = 0
    frame_count = 0
    current_time = start_time

    while current_time <= end_time:
        cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
        ret, frame = cap.read()
        if not ret:
            break

        total_frames += 1
        label = classify_frame(frame, model)

        if label == 0:
            ad_frames += 1

        current_time += frame_interval
        frame_count += 1

    cap.release()
    ad_percentage = (ad_frames / total_frames) * 100 if total_frames > 0 else 0.0
    return ad_percentage


def detect_ad_scenes_from_segments(video_path, model, name, threshold):
    scenes = detect_scenes(video_path)
    res = []
    print(f"Analyze by model {name}")
    for start, end in scenes:
        result = process_video_segments_after_(video_path, model, start, end)
        print(name, start, end, result)
        if result > threshold:
            res.append((start, end))
    return res


def detect_ad_scenes_from_segments_and_get_all_results_to_logs(video_path, scenes, model, name, log_file):
    result_dict = {}
    for start, end in scenes:
        result = process_video_segments_weigth(video_path, model, start, end)
        log_file.write(f"{name} {start} {end} {result}\n")
        log_file.flush()
        result_dict[(start, end)] = result
    return result_dict


def detect_ad_scenes_from_segments_and_get_all_results(video_path, scenes, model):
    result_dict = {}
    for start, end in scenes:
        result = process_video_segments_after_(video_path, model, start, end)
        result_dict[(start, end)] = result
    return result_dict


def detect_scenes(video_path, threshold=65.0):
    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))

    video_manager.set_downscale_factor()
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)

    scene_list = scene_manager.get_scene_list()
    scene_times = [(start.get_seconds(), end.get_seconds()) for start, end in scene_list]
    video_manager.release()
    return scene_times
