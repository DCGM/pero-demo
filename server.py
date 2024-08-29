import os
import uuid
import base64
import argparse
from collections import defaultdict

import numpy as np
from flask import Flask, send_from_directory, send_file, json, request

from pero_ocr.core.layout import PageLayout, RegionLayout
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

        lines = convert_lines(page_layout)

        data = {
            "image_id": request_id,
            "width": width,
            "height": height,
            "lines": lines
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


@app.route('/get_music/<string:request_id>', defaults={'line_id': None})
@app.route('/get_music/<string:request_id>/<string:line_id>')
def get_music(request_id, line_id):
    midi_file_path = get_midi_path(request_id, line_id)

    if os.path.isfile(midi_file_path):
        return send_file(midi_file_path)
    else:
        return app.response_class(
            status=204
        )


def get_image_path(request_id):
    return os.path.join(configuration["requests"]["upload_path"], f"{request_id}.jpg")


def get_xml_path(request_id):
    return os.path.join(configuration["requests"]["result_path"], f"{request_id}.xml")


def get_logits_path(request_id):
    return os.path.join(configuration["requests"]["logits_path"], f"{request_id}.logits")


def get_errors_path(request_id):
    return os.path.join(configuration["requests"]["errors_path"], f"{request_id}.txt")


def get_midi_path(request_id, line_id=None):
    file_name = f"{request_id}.mid" if line_id is None else f"{request_id}_{line_id}.mid"
    return os.path.join(configuration["requests"]["music_path"], file_name)


def get_music_xml_path(request_id):
    return os.path.join(configuration["requests"]["music_path"], f"{request_id}.xml")


def convert_lines(page_layout):
    lines = []

    counts = defaultdict(int)
    converters = {
        "Obrázek": (convert_image, "image"),
        "Kreslený humor/karikatura/komiks": (convert_image, "image"),

        "Fotografie": (convert_photo, "photo"),

        "Graf": (convert_graph, "graph"),

        "Iniciála": (convert_initial, "initial"),

        "Mapa": (convert_map, "map"),

        "Ozdobný nápis": (convert_decorative_text, "decorative_text"),

        "Razítko": (convert_stamp, "stamp"),

        "QR a čárový kód": (convert_code, "code"),

        "Schéma": (convert_schema, "schema"),
        "Půdorys": (convert_schema, "schema"),
        "Ostatní výkresy": (convert_schema, "schema"),
        "Geometrické výkresy": (convert_schema, "schema"),

        "Erb/cejch/logo/symbol": (convert_other, "other"),
        "Ex libris": (convert_other, "other"),
        "Ostatní knižní dekor": (convert_other, "other"),
        "Signet": (convert_other, "other"),
        "Viněta": (convert_other, "other"),
        "Vlys": (convert_other, "other"),
    }

    for region in page_layout.regions:
        if region.category in {"text", None}:
            for line in region.lines:
                if line.category in {"text", None}:
                    lines.append(convert_line(line))

        elif region.category in converters:
            converter, category = converters[region.category]
            counts[category] += 1
            lines.append(converter(region, counts[category]))

        elif region.category == "Notový zápis":
            lines.append(convert_music(region))

    return lines


def convert_line(line):
    return {
        "id": line.id,
        "text": line.transcription,
        "np_points": [[int(coordinates[0]), int(coordinates[1])] for coordinates in line.polygon],
        "np_heights": list(line.heights),
        "np_confidences": calculate_line_confidence(line),
        "ligatures_mapping": [[x] for x in range(len(line.transcription))],
        "category": "text"
    }


def convert_image(region, index):
    return convert_region_object(region, "image", text=f"[Image #{index}]", use_region_transcription=True)


def convert_photo(region, index):
    return convert_region_object(region, "photo", text=f"[Photo #{index}]", use_region_transcription=True)


def convert_music(region):
    return convert_region_object(region, "music")


def convert_graph(region, index):
    return convert_region_object(region, "graph", text=f"[Graph #{index}]", use_region_transcription=True)


def convert_initial(region, index):
    return convert_region_object(region, "initial", text=f"[Initial #{index}]")


def convert_map(region, index):
    return convert_region_object(region, "map", text=f"[Map #{index}]", use_region_transcription=True)


def convert_decorative_text(region, index):
    return convert_region_object(region, "decorative_text", text=f"[Decorative text #{index}]", use_region_transcription=True)


def convert_stamp(region, index):
    return convert_region_object(region, "stamp", text=f"[Stamp #{index}]")


def convert_code(region, index):
    return convert_region_object(region, "code", text=f"[QR/Barcode #{index}]")


def convert_schema(region, index):
    return convert_region_object(region, "schema", text=f"[Schema #{index}]", use_region_transcription=True)


def convert_other(region, index):
    return convert_region_object(region, "other", text=f"[Other object #{index}]")


def convert_region_object(region, category, text="", use_region_transcription=False):
    y1 = min([point[1] for point in region.polygon])
    y2 = max([point[1] for point in region.polygon])

    height = y2 - y1

    if region.transcription is not None and use_region_transcription:
        text = f"{text} {region.transcription}"

    return {
        "id": region.id,
        "text": text,
        "np_points": [[int(coordinates[0]), int(coordinates[1])] for coordinates in region.polygon],
        "np_heights": [float(height), 0],
        "np_confidences": [1.0] * len(text),
        "ligatures_mapping": [[x] for x in range(len(text))],
        "category": category
    }


# def convert_music(region):
#     y1 = min([point[1] for point in region.polygon])
#     y2 = max([point[1] for point in region.polygon])
#
#     height = y2 - y1
#
#     text = ""
#
#     return {
#         "id": region.id,
#         "text": text,
#         "np_points": [[int(coordinates[0]), int(coordinates[1])] for coordinates in region.polygon],
#         "np_heights": [float(height), 0],
#         "np_confidences": [1.0] * len(text),
#         "ligatures_mapping": [[x] for x in range(len(text))],
#         "category": "music"
#     }


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

    confidences = [float(confidence) for confidence in confidences]

    return confidences


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
    configuration["requests"]["music_path"] = get_absolute_path(config_path, configuration["requests"]["music_path"])


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
