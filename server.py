import os
import uuid
import base64
import argparse
import numpy as np
from flask import Flask, send_from_directory, send_file, json, request

from pero_ocr.core.layout import PageLayout
from pero_ocr.core.confidence_estimation import get_line_confidence

import config_helper

configuration = None
app = Flask(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config-file', required=True, help='Path to configuration file.')
    args = parser.parse_args()
    return args


@app.route('/', defaults={'filename': 'index.html'})
@app.route('/<path:filename>')
def application(filename):
    return send_from_directory('./', filename)


@app.route('/upload_image', methods=["POST"])
def upload_image():
    encoded_image = request.json["image"]

    request_id = uuid.uuid4().hex
    image_file_path = get_image_path(request_id)
    save_image_result = save_encoded_image(encoded_image, image_file_path)

    if not save_image_result:
        save_error_file(request_id)

    data = {"request_id": request_id}
    response = app.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route('/get_image/<string:request_id>')
def get_image(request_id):
    image_file_path = get_image_path(request_id)
    return send_file(image_file_path, as_attachment=True)


@app.route('/get_status/<string:request_id>')
def get_status(request_id):
    image_file_path = get_image_path(request_id)
    xml_file_path = get_xml_path(request_id)
    error_file_path = get_errors_path(request_id)

    status = 404

    if os.path.isfile(image_file_path):
        status = 202

    if os.path.isfile(error_file_path):
        status = 500

    if os.path.isfile(xml_file_path):
        status = 200
    
    response = app.response_class(
        status=status,
    )

    return response


@app.route('/get_lines/<string:request_id>')
def get_lines(request_id):
    xml_file_path = get_xml_path(request_id)
    logits_file_path = get_logits_path(request_id)

    if xml_file_path:
        page_layout = PageLayout(file=xml_file_path)
        height, width = page_layout.page_size

        page_layout.load_logits(logits_file_path)

        # TODO: Calculate confidences
        data = {
            "image_id": request_id,
            "width": width,
            "height": height,
            "lines": [{
                "id": line.id,
                "text": line.transcription,
                "np_points": [[int(coordinates[0]), int(coordinates[1])] for coordinates in line.polygon],
                "np_heights": list(line.heights),
                "np_confidences": calculate_line_confidence(line),
                "ligatures_mapping": [[x] for x in range(len(line.transcription))]
            } for line in page_layout.lines_iterator()]
        }

        response = app.response_class(
            response=json.dumps(data),
            status=200,
            mimetype='application/json'
        )

    else:
        response = app.response_class(
            status=404
        )        

    return response


def get_image_path(request_id):
    return os.path.join(configuration["requests"]["upload_path"], f"{request_id}.jpg")


def get_xml_path(request_id):
    return os.path.join(configuration["requests"]["result_path"], f"{request_id}.xml")


def get_logits_path(request_id):
    return os.path.join(configuration["requests"]["logits_path"], f"{request_id}.logits")


def get_errors_path(request_id):
    return os.path.join(configuration["requests"]["errors_path"], f"{request_id}.txt")


def calculate_line_confidence(line):
    if line.transcription is not None and line.transcription != "":
        char_map = dict([(c, i) for i, c in enumerate(line.characters)])
        c_idx = np.asarray([char_map[c] for c in line.transcription])
        
        try:
            confidences = get_line_confidence(line, c_idx)
    
        except ValueError:
            confidences = np.ones(len(line.transcription))
    
    else:
        confidences = np.array([])

    return list(confidences)


def save_error_file(request_id):
    path = get_errors_path(request_id)
    with open(path, 'w') as file:
        pass


def save_encoded_image(encoded_image, path):
    decoded_image, extension = decode_image(encoded_image)

    if decoded_image is not None:
        save_decoded_image(decoded_image, path)
        result = True
    else:
        result = False

    return result


def save_decoded_image(decoded_image, path):
    with open(path, "wb") as file: 
        file.write(decoded_image)


def decode_image(encoded_image):
    png_prefix = "data:image/png;base64,"
    jpg_prefix = "data:image/jpeg;base64,"

    if encoded_image.startswith(png_prefix):
        encoded_image = encoded_image[len(png_prefix):]
        extension = "png"

    elif encoded_image.startswith(jpg_prefix):
        encoded_image = encoded_image[len(jpg_prefix):]
        extension = "jpg"

    else:
        encoded_image = None
        extension = None

    if encoded_image is not None:
        decoded_image = base64.decodebytes(bytes(encoded_image, "utf-8"))
    else:
        decoded_image = None

    return decoded_image, extension


def create_dirs(path):
    os.makedirs(path, exist_ok=True)


def get_absolute_path(config_path, path):
    config_dir = os.path.dirname(config_path)
    return os.path.join(config_dir, path)


def make_absolute_paths(config_path):
    global configuration

    configuration["ssl"]["certificate_path"] = get_absolute_path(config_path, configuration["ssl"]["certificate_path"])
    configuration["ssl"]["private_key_path"] = get_absolute_path(config_path, configuration["ssl"]["private_key_path"])

    configuration["requests"]["upload_path"] = get_absolute_path(config_path, configuration["requests"]["upload_path"])
    configuration["requests"]["result_path"] = get_absolute_path(config_path, configuration["requests"]["result_path"])
    configuration["requests"]["logits_path"] = get_absolute_path(config_path, configuration["requests"]["logits_path"])
    configuration["requests"]["errors_path"] = get_absolute_path(config_path, configuration["requests"]["errors_path"])


def main():
    args = parse_args()

    global configuration
    configuration = config_helper.parse_configuration(args.config_file)
    make_absolute_paths(os.path.abspath(args.config_file))

    host = configuration["common"]["host"]
    port = configuration["common"]["port"]
    debug = configuration["common"]["debug"]

    certificate_path = configuration["ssl"]["certificate_path"]
    private_key_path = configuration["ssl"]["private_key_path"]

    create_dirs(configuration["requests"]["upload_path"])
    create_dirs(configuration["requests"]["result_path"])
    create_dirs(configuration["requests"]["logits_path"])
    create_dirs(configuration["requests"]["errors_path"])

    app.run(host=host, port=port, debug=debug, ssl_context=(certificate_path, private_key_path), threaded=True)


if __name__ == '__main__':
    main()
