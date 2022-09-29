width = 1920
height = 1080

var videoConstraints = {
    video: {
        width: { ideal: width },
        height: { ideal: height },
        facingMode: { ideal: "environment" }
    }
}

// Grab elements, create settings, etc.
var preview_canvas = document.getElementById('canvas');
var video = document.getElementById('video');
var original_image_canvas = document.getElementById('original-image')
var image = null;
var currentDeviceId = null;
var devicesId = []
var requestId = null;

var controller = new Controller();
var text_lines_editor = new TextLinesEditor(document.getElementById('map-container'));

document.getElementById("snap").addEventListener("click", function () {
    clear();
    snap();
});

document.getElementById("change").addEventListener("click", function () {
    changeCamera();
});

document.getElementById("send").addEventListener("click", function () {
    send();
});

window.addEventListener('popstate', (event) => {    
    var url = new URL(window.location);
    requestId = url.searchParams.get("id");

    if (requestId == null) {
        controller.goStart();
    }
    else {
        controller.currentPage = 2;
        controller.showCurrentPage();
    }
});


async function send() {
    $('#uploadingMessage').collapse('show');

    upload_url = window.location.origin + '/upload_image'

    let response = await fetch(upload_url, {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ image: image })
    })

    data = await response.json();
    requestId = data['request_id'];
    window.history.pushState(null, "PERO App", '?id=' + requestId);

    controller.goForward();
}

function gotDevices(mediaDevices) {
    devicesId = [];
    mediaDevices.forEach(mediaDevice => {
        if (mediaDevice.kind === 'videoinput') {
            devicesId.push(mediaDevice.deviceId);
        }
    });
}

function snap() {
    preview_canvas.width = video.offsetWidth;
    preview_canvas.height = video.offsetHeight;
    
    video_placement = calculateVideoPlacement(video, preview_canvas);
    preview_canvas.getContext('2d').drawImage(video, video_placement.x, video_placement.y, video_placement.width, video_placement.height);

    resolution = getVideoResolution(video);
    original_image_canvas.width = resolution.width;
    original_image_canvas.height = resolution.height;
    original_image_canvas.getContext('2d').drawImage(video, 0, 0);

    // base64 encoded image
    image = original_image_canvas.toDataURL('image/jpeg', 0.85);

    //showOutput(image);
}

function clear() {
    preview_canvas.getContext('2d').clearRect(0, 0, preview_canvas.width, preview_canvas.height);
    original_image_canvas.getContext('2d').clearRect(0, 0, original_image_canvas.width, original_image_canvas.height)
}

function startCamera() {
    if (devicesId.length > 0) {
        video.setAttribute('autoplay', '');
        video.setAttribute('muted', '');
        video.setAttribute('playsinline', '');

        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            startVideoStream();

            setEnabled('snap');

            if (devicesId.length > 1) {
                setEnabled('change');
            }
        }
        else {
            alert("Přístup ke kameře zamítnut.");
        }
    }
    else {
        alert("Nebyla nalzena žádná kamera.");
    }
}

function stopCamera() {
    stopVideoStream();

    setDisabled('change');
    setDisabled('snap');
}

function startVideoStream() {
    navigator.mediaDevices.getUserMedia(videoConstraints).then(function (stream) {
        video.srcObject = stream;
        video.play();

        currentDeviceId = getDeviceId(video);
    });
}

function stopVideoStream() {
    stream = video.srcObject
    stream.getTracks().forEach(function (track) {
        if (track.readyState == 'live') {
            track.stop();
        }
    });

    video.srcObject = null;
}

function changeCamera() {
    index = devicesId.indexOf(currentDeviceId);

    if (index >= 0) {
        next = (index + 1) % devicesId.length;
        videoConstraints.video.deviceId = { exact: devicesId[next] };
        delete videoConstraints.video.facingMode;
    }

    stopVideoStream();
    startVideoStream();
}

function calculateVideoPlacement(video, canvas) {
    canvas_width = canvas.width;
    canvas_height = canvas.height;

    video_resolution = getVideoResolution(video);
    stream_width = video_resolution.width
    stream_height = video_resolution.height

    scale = canvas_width / stream_width;

    if (stream_height * scale > canvas_height) {
        scale = canvas_height / stream_height;
    }

    width = stream_width * scale;
    height = stream_height * scale;

    x = (canvas_width - width) / 2;
    y = (canvas_height - height) / 2;

    return { x: x, y: y, width: width, height: height };
}

function getVideoResolution(video) {
    stream = video.srcObject;
    stream_width = stream.getVideoTracks()[0].getSettings().width;
    stream_height = stream.getVideoTracks()[0].getSettings().height;

    return { width: stream_width, height: stream_height }
}

function getDeviceId(video) {
    stream = video.srcObject;
    deviceId = stream.getVideoTracks()[0].getSettings().deviceId;
    return deviceId;
}

function setEnabled(name) {
    setDisabledState(name, false);
}

function setDisabled(name) {
    setDisabledState(name, true);
}

function setDisabledState(name, value) {
    document.getElementById(name).disabled = value;
}

function cameraScreenStart() {
    navigator.mediaDevices.enumerateDevices()
        .then(gotDevices)
        .then(startCamera);
}

function appStart() {
    var url = new URL(window.location);
    requestId = url.searchParams.get("id");

    if (requestId != null) {
        // go to result page
        controller.currentPage = 2;
    }
}

function waitForResult() {
    var url = new URL(window.location);
    requestId = url.searchParams.get("id");

    var resultChecker = setInterval(function () {
        checkStatus(requestId).then(requestStatus => {
            if (requestStatus == 200) {
                clearInterval(resultChecker);
                text_lines_editor.change_image(requestId);
                
                controller.goForward();
            }
            else if (requestStatus == 202) {
                // continue checking
            }
            else if (requestStatus == 404) {
                clearInterval(resultChecker);
                alert("Naznámý požadavek. ID: " + requestId);
                controller.goStart();
            }
            else if (requestStatus == 500) {
                clearInterval(resultChecker);
                alert("Při zpracování Vašeho požadavku došlo k chybě. Zkuste to prosím znovu. ID: " + requestId);
                controller.goStart();
            }
            else {
                clearInterval(resultChecker);
                alert("Neočekávaný stav (" + requestStatus + ") požadavku. ID: " + requestId);
                controller.goStart();
            }
        });
    }, 2000);
}

function checkRequest() {
    checkStatus(requestId).then(requestStatus => {
        if (requestStatus == 200) {
            text_lines_editor.change_image(requestId);
            
            controller.goForward();
        }
        else {
            waitForResult(requestId);
        }
    });
}

async function checkStatus(requestId) {
    let response = await fetch("/get_status/" + requestId);
    return response.status;
}

function showResults() {
    updateLeafletHeight();
    updateTextContainerHeight();
}

function updateLeafletHeight() {  
    container = document.getElementById('app-page-content-3-leaflet');
    leaflet = document.getElementById('result-leaflet');
    leaflet.style.height = container.style.maxHeight;
}

function updateTextContainerHeight() {
    container = document.getElementById('app-page-content-3-text');
    text = document.getElementById('text-container');
    text.style.height = container.style.maxHeight;
}

function updateVideoHeight() {
    container = document.getElementById('app-page-content-0');
    video.style.height = container.style.maxHeight;
}

function updateCanvasHeight() {
    container = document.getElementById('app-page-content-1');
    canvas.style.height = container.style.maxHeight;
}

function updateContentDimensions() {
    height =  window.innerHeight;
    
    video_height = 0.8;
    controls_height = 0.15;
    leaflet_height = 0.47;
    text_height = 0.33;


    video_max_height = height * video_height;
    controls_max_height = height * controls_height;
    text_max_height = height * text_height;
    leaflet_max_height = height * leaflet_height;

    document.getElementById('app-page-content-0').style.maxHeight = video_max_height + "px";
    document.getElementById('app-page-content-1').style.maxHeight = video_max_height + "px";
    document.getElementById('app-page-content-2').style.maxHeight = video_max_height + "px";
    document.getElementById('app-page-content-3').style.maxHeight = video_max_height + "px";
    document.getElementById('app-page-controls-0').style.maxHeight = controls_max_height + "px";
    document.getElementById('app-page-controls-1').style.maxHeight = controls_max_height + "px";
    document.getElementById('app-page-controls-2').style.maxHeight = controls_max_height + "px";
    document.getElementById('app-page-controls-3').style.maxHeight = controls_max_height + "px";

    document.getElementById('loading-svg').style.maxHeight = video_max_height + "px";

    document.getElementById('app-page-content-3-leaflet').style.maxHeight = leaflet_max_height + "px";
    document.getElementById('app-page-content-3-text').style.maxHeight = text_max_height + "px";
}

window.addEventListener('resize', function () {
    updateContentDimensions(); 
    updateVideoHeight();
    updateCanvasHeight();
});

updateContentDimensions();
updateVideoHeight();
updateCanvasHeight();

controller.startApp()
