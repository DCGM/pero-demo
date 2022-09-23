# PERO Demo App
Demo web application used to showcase PERO OCR. In the application user captures an image with text, uploads it to the server, and when the result is ready it is shown to the user. When the server recieves new image it is processed using [PERO OCR](https://github.com/DCGM/pero-ocr) pipeline.

## How to run this demo
To run this demo it is needed to run the ocr pipeline (`ocr_pipeline.py`) and server (`server.py`).

### Server
The `server.py` script requires server config INI file specified by `--config-file` command line argument. Here is an example configuration file:

```
[common]
host = 127.0.0.1    ; use 0.0.0.0 to access from the Internet
port = 8001
debug = False

[ssl]
certificate_path = certs/cert1.pem       ; path to the server certificate
private_key_path = certs/privkey1.pem    ; path to the server private key

[requests]
upload_path = images    ; directory where uploaded images are stored
result_path = xmls      ; directory for storing OCR results (PAGE XMLs)
logits_path = logits    ; directory for storing logits to calculate confidences
errors_path = errors    ; if processing of an image fails, an empty text file is created here to signalize it to the server
```


### OCR pipeline
The ocr_pipeline.py script requires two config INI files. The first (specified by `--server-config`) is the same as required by the server. The second (specified by `--pipeline-config`) is the PERO OCR config file with definition how the images are processed.
