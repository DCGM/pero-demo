import os
import sys
import argparse
import config_helper
import configparser
import cv2
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

from pero_ocr.document_ocr.layout import PageLayout
from pero_ocr.document_ocr.page_parser import PageParser


import faulthandler

class NewFileHandler(FileSystemEventHandler):
    def __init__(self, page_parser, output_xmls_path, output_logits_path, output_error_path):
        self.page_parser = page_parser
        self.output_xmls_path = output_xmls_path
        self.output_logits_path = output_logits_path
        self.output_error_path = output_error_path

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
                page_layout = self.page_parser.process_page(image, page_layout)
                page_layout.to_pagexml(output_xml_path)
                page_layout.save_logits(output_logits_path)

            except:
                log("Exception raised during processing. Saving error file.", file_id)
                self.save_error_file(file_id)

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


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server-config', help='Path to server config file.', required=True)
    parser.add_argument('-p', '--pipeline-config', help='Path to OCR pipeline config file.', required=True)
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

    log("Parsing OCR pipeline configuration")
    pipeline_config = configparser.ConfigParser()
    pipeline_config.read(args.pipeline_config)

    log("Initializing PageParser")
    page_parser = PageParser(pipeline_config, config_path=os.path.dirname(args.pipeline_config))

    log("Initializing observer and handler")
    observer = Observer()
    event_handler = NewFileHandler(page_parser, output_path, logits_path, errors_path)

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
