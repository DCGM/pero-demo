import os
import cv2
import sys
import time
import torch
import base64
import argparse
import requests
import traceback
import numpy as np
import configparser
import faulthandler
import config_helper
from functools import partial

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from multiprocessing import Pool

from pero_ocr.core.layout import PageLayout
from pero_ocr.document_ocr.page_parser import PageParser
from pero_ocr.music.music_exporter import MusicPageExporter


class NewFileHandler(FileSystemEventHandler):
    def __init__(self, page_parser, music_exporter, output_xmls_path, output_logits_path, output_error_path, pad_to_a4=False):
        self.page_parser = page_parser
        self.music_exporter = music_exporter
        self.output_xmls_path = output_xmls_path
        self.output_logits_path = output_logits_path
        self.output_error_path = output_error_path
        self.pad_to_a4 = pad_to_a4

        self._caption_categories = ["Obrázek", "Kreslený humor/karikatura/komiks", "Fotografie", "Graf", "Mapa",
                                    "Ozdobný nápis", "Schéma", "Půdorys", "Ostatní výkresy", "Geometrické výkresy"]

        self._api_key = self.load_api_key()
        self.max_image_size = 512

    def load_api_key(self):
        api_key_file = os.path.join("api_key.txt")
        with open(api_key_file, "r") as file:
            return file.readline().strip()

    def on_created(self, event):
        new_file_path = event.src_path
        _, file_name = os.path.split(new_file_path)
        file_id, _ = os.path.splitext(file_name)
        log("New file detected", file_id)
        
        if new_file_path.endswith(".jpg"):
            log("Processing started", file_id)
            self.process_file(file_id, new_file_path)
            log("Processing finished", file_id)

    def process_file(self, file_id, image_path):
        attempts = 3
        delay = 1
        
        image = cv2.imread(image_path, 1)

        if image is None:
            for i in range(attempts):
                time.sleep(delay)
                image = cv2.imread(image_path, 1)

                if image is not None:
                    break

        if image is None:
            log("Cannot load image. Saving error file.", file_id)
            self.save_error_file(file_id)

        else:
            output_xml_path = self.get_xml_file_path(file_id)
            output_logits_path = self.get_logits_file_path(file_id)

            try:
                page_layout = PageLayout(id=file_id, page_size=(image.shape[0], image.shape[1]))
                
                if self.pad_to_a4:
                    image = self.add_padding(image)

                page_layout = self.page_parser.process_page(image, page_layout)

                self.generate_image_captions(image, page_layout)

                page_layout.to_pagexml(output_xml_path)
                page_layout.save_logits(output_logits_path)

                self.music_exporter.process_page(page_layout)

            except:
                log("Exception raised during processing:", file_id)
                log(traceback.format_exc(), file_id)
                log("Saving error file.", file_id)
                self.save_error_file(file_id)

    def add_padding(self, image):
        a4_height, a4_width = 2970, 2100
        a4_ratio = a4_width / a4_height

        image_height, image_width = image.shape[:2]
        image_ratio = image_width / image_height

        if image_ratio > a4_ratio:
            target_height = round(image_width / a4_ratio)
            target_width = image_width
        else:
            target_height = image_height
            target_width = round(image_height * a4_ratio)

        target_image = np.full((target_height, target_width, 3), 255, dtype=np.uint8)
        target_image[:image_height, :image_width] = image

        return target_image

    def generate_image_captions(self, page_image, page_layout):
        regions = []
        images = []
        for region in page_layout.regions:
            if region.category in self._caption_categories:
                y1 = round(min([point[1] for point in region.polygon]))
                y2 = round(max([point[1] for point in region.polygon]))
                x1 = round(min([point[0] for point in region.polygon]))
                x2 = round(max([point[0] for point in region.polygon]))

                original_width = x2 - x1
                original_height = y2 - y1

                image = page_image[y1:y2, x1:x2]

                if original_width > self.max_image_size or original_height > self.max_image_size:
                    if original_width > original_height:
                        image = cv2.resize(image, (self.max_image_size, round(self.max_image_size * original_height / original_width)))
                    else:
                        image = cv2.resize(image, (round(self.max_image_size * original_width / original_height), self.max_image_size))

                if image.size == 0:
                    log(f"Empty region detected {region.id} ({region.category}): {x1},{y1} {x2},{y2}")

                else:
                    images.append(image)
                    regions.append(region)

        processing_function = partial(generate_image_caption, api_key=self._api_key)

        with Pool(4) as p:
            image_captions = p.map(processing_function, images)

        for region, image_caption in zip(regions, image_captions):
            region.transcription = image_caption

    def save_error_file(self, file_id):
        path = self.get_error_file_path(file_id)
        with open(path, 'w') as file:
            pass

    def get_error_file_path(self, file_id):
        return self.get_file_path(self.output_error_path, file_id, ".txt")

    def get_logits_file_path(self, file_id):
        return self.get_file_path(self.output_logits_path, file_id, ".logits")

    def get_xml_file_path(self, file_id):
        return self.get_file_path(self.output_xmls_path, file_id, ".xml")

    def get_file_path(self, path, file_id, extension):
        return os.path.join(path, file_id + extension)

def generate_image_caption(image, api_key):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Give me one short sentence describing the image."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encode_image(image)}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    try:
        image_caption = response.json()["choices"][0]["message"]["content"]
    except:
        image_caption = ""

    return image_caption

def encode_image(image):
    image_jpg = cv2.imencode('.jpg', image)[1]
    image_base64 = base64.b64encode(image_jpg).decode('utf-8')
    return image_base64


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server-config', help='Path to server config file.', required=True)
    parser.add_argument('-p', '--pipeline-config', help='Path to OCR pipeline config file.', required=True)
    parser.add_argument('--pad-to-a4', help='Pad images to A4 format.', action='store_true')
    args = parser.parse_args()
    return args


def log(message, log_source="SCRIPT"):
    print(f"[{log_source}|{datetime.utcnow()}] {message}")


def get_absolute_path(config_path, path):
    config_dir = os.path.dirname(config_path)
    return os.path.join(config_dir, path)

def main():
    faulthandler.enable()

    log("Script started")
    args = parse_arguments()
    
    log("Parsing server configuration")
    server_config = config_helper.parse_configuration(args.server_config)
    abs_config_path = os.path.abspath(args.server_config)
    input_path = get_absolute_path(abs_config_path, server_config["requests"]["upload_path"])
    output_path = get_absolute_path(abs_config_path, server_config["requests"]["result_path"])
    logits_path = get_absolute_path(abs_config_path, server_config["requests"]["logits_path"])
    errors_path = get_absolute_path(abs_config_path, server_config["requests"]["errors_path"])
    music_path = get_absolute_path(abs_config_path, server_config["requests"]["music_path"])

    log("Parsing OCR pipeline configuration")
    pipeline_config = configparser.ConfigParser()
    pipeline_config.read(args.pipeline_config)

    log("Initializing PageParser")
    page_parser = PageParser(pipeline_config, torch.device('cuda'), config_path=os.path.dirname(args.pipeline_config))

    log("Initializing MusicPageExporter")
    music_exporter = MusicPageExporter(output_folder=music_path, export_midi=True, export_musicxml=True)

    log("Initializing observer and handler")
    observer = Observer()
    event_handler = NewFileHandler(page_parser, music_exporter, output_path, logits_path, errors_path, pad_to_a4=args.pad_to_a4)

    observer.schedule(event_handler, path=input_path)
    observer.start()

    # sleep until keyboard interrupt, then stop + rejoin the observer
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    return 0


if __name__ == "__main__":
    sys.exit(main())
