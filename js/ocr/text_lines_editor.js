
yx = L.latLng;
xy = function(x, y) {
    if (L.Util.isArray(x)) {    // When doing xy([x, y]);
        return yx(x[1], x[0]);
    }
    return yx(y, x);  // When doing xy(x, y);
};

function rgb(r, g, b){
  return "rgb("+r+","+g+","+b+")";
};

class TextLinesEditor
{
    constructor(container)
    {
        this.container = container;
        this.container.innerHTML = "<div id='result-leaflet' class='editor-map'></div><div class='status'></div>";
        this.map_element = this.container.getElementsByClassName("editor-map")[0];
        this.active_line = false;
        this.focus_to = null;
        
        this.text_container = document.getElementById('text-container');
        
        this.worst_confidence = 0;
    }

    swap_ignore_line_button_blueprint(){
        // if (this.active_line.for_training_checkbox.checked){
        //     this.ignore_btn.innerHTML  = '<i class="fas fa-minus-circle"></i> Ignore line';
        // }
        // else {
        //     this.ignore_btn.innerHTML  = '<i class="fas fa-minus-circle"></i> Unignore line';
        // }

        // try {
        //     //this.active_line.container.focus();

        //     console.log("SCROLL");
        //     scrollToElm(this.text_container, this.active_line.container, 500);

        //     console.log(active_line.container);
        // }
        // catch(err) {
        //     console.log("ERR");
        // }
        
        scrollToElm(this.text_container, this.active_line.container, 0.5);
    }


    swap_delete_line_button_blueprint(){
        // if (this.active_line.valid){
        //     this.delete_btn.innerHTML  = '<i class="far fa-trash-alt"></i> Delete line';
        //     this.delete_btn.className  = 'btn btn-danger';
        // }
        // else{
        //     this.delete_btn.innerHTML  = '<i class="fas fa-undo"></i> Restore line';
        //     this.delete_btn.className  = 'btn btn-primary';
        // }

        try {
            this.active_line.container.focus();
        }
        catch(err) {
        }
    }

    ignore_line_btn_action(button=false){
        if (this.active_line != false){
            if (button) {
                this.active_line.for_training_checkbox.checked = !this.active_line.for_training_checkbox.checked;
            }

            let training_flag;
            if (this.active_line.for_training_checkbox.checked){training_flag = 1;}else{training_flag = 0;}

            let text_lines_editor = this;
            let route = Flask.url_for('ocr.training_line', {'line_id': this.active_line.id, 'training_flag': training_flag});
            this.ignore_btn.disabled = true;
            this.active_line.for_training_checkbox.disabled = true;
            $.ajax({
                type: "POST",
                url: route,
                data: {'line_id': this.active_line.id, 'training_flag': training_flag},
                dataType: "json",
                error: function(xhr, ajaxOptions, ThrownError){
                    text_lines_editor.active_line.for_training_checkbox.checked = ! text_lines_editor.active_line.for_training_checkbox.checked;
                    text_lines_editor.swap_ignore_line_button_blueprint();
                    text_lines_editor.ignore_btn.disabled = false;
                    text_lines_editor.active_line.for_training_checkbox.disabled = false;
                    alert('Unable to set training flag. Check your remote connection.');
                },
                success: function(xhr, ajaxOptions) {
                    text_lines_editor.swap_ignore_line_button_blueprint();
                    text_lines_editor.ignore_btn.disabled = false;
                    text_lines_editor.active_line.for_training_checkbox.disabled = false;
                }
            });
        }
    }

    set_line_style(line){
        var conf = (line.line_confidence-this.worst_confidence) / (1-this.worst_confidence);
        // console.log('X ' + conf + ' ' + this.worst_confidence + ' ' + line.annotated);
        // console.log(line.edited);
        // console.log(line.valid);

        var color = '';
        if( !line.valid){
            color = rgb(16, 16, 16);
        } else if(line.edited){
            color = '#ffcc54'
        } else if(line.annotated){
            color = "#028700";
        } else {
            color = rgb((1-conf) * 255, 16, conf * 255);
        }
        if(line.focus){
            line.polygon.setStyle({ color: color, opacity: 1, fillColor: color, fillOpacity: 0.15, weight: 2});
            line.container.style.border = "solid teal";
            line.container.style.borderRadius = "10px";

        } else {
            line.polygon.setStyle({ color: color, opacity: 0.5, fillColor: color, fillOpacity: 0.1, weight: 1});
            line.container.style.border = "";
            line.container.style.borderRadius = "0px";
        }
    }

    delete_line_btn_action(){
        if (this.active_line != false){
            this.active_line.valid = !this.active_line.valid;

            let delete_flag;
            if (this.active_line.valid){delete_flag = 0;}else{delete_flag = 1;}

            let text_lines_editor = this;
            let route = Flask.url_for('ocr.delete_line', {'line_id': this.active_line.id, 'delete_flag': delete_flag});
            this.delete_btn.disabled = true;
            $.ajax({
                type: "POST",
                url: route,
                data: {'line_id': this.active_line.id, 'delete_flag': delete_flag},
                dataType: "json",
                error: function(xhr, ajaxOptions, ThrownError){
                    text_lines_editor.active_line.valid = !text_lines_editor.active_line.valid;
                    text_lines_editor.active_line.mutate();
                    text_lines_editor.swap_delete_line_button_blueprint();
                    text_lines_editor.delete_btn.disabled = false;
                    alert('Unable to set delete flag. Check your remote connection.');
                },
                success: function(xhr, ajaxOptions) {
                    text_lines_editor.active_line.mutate();
                    text_lines_editor.swap_delete_line_button_blueprint();
                    text_lines_editor.delete_btn.disabled = false;
                }
            });
            this.active_line.container.focus();
        }
    }

    change_image(image_id, change_url_callback, line_id)
    {
        if (typeof this.lines !== 'undefined')
        {
            let unsaved_lines = false;
            for (let l of this.lines)
            {
                if (l.edited)
                {
                    unsaved_lines = true;
                }
            }
            if (unsaved_lines)
            {
                if (confirm("Save changes?"))
                {
                    this.save_annotations();
                }
            }
        }
        this.focus_to = line_id;
        this.get_image(image_id);
    }

    async get_image(image_id)
    {
        let route = "/get_lines/" + image_id;
        while (this.text_container.firstChild)
        {
            this.text_container.firstChild.remove();
        }
        let response = fetch(route)
            .then(res => res.json());

        let data = await response;

        if( data['image_id'] != image_id){
            return;
        }

        this.image_id = data['image_id'];
        this.width = data['width'];
        this.height = data['height'];
        this.active_line = false;
        this.lines = [];

        if (this.map)
        {
            this.map.off();
            this.map.remove();
        }
        this.map = L.map(this.map_element, {
            crs: L.CRS.Simple,
            minZoom: -3,
            maxZoom: 3,
            center: [this.width/2, this.height/2],
            zoom: 0,
            editable: true,
            fadeAnimation: false,
            zoomAnimation: true,
            zoomSnap: 0
        });


        let bounds = [xy(0, -this.height), xy(this.width, 0)];
        //this.map.setView(xy(this.width / 2, -this.height / 2), -2);
        this.map.fitBounds(bounds);
        L.imageOverlay("/get_image/" + image_id, bounds).addTo(this.map);

        let self = this;
        let observer = new MutationObserver(function(mutations){
          mutations.forEach(function(m){
              self.set_line_style(self.lines[ m.target.id]);
          });
        });

        let i = 0;
        let debug_line_container = document.getElementById('debug-line-container');
        let debug_line_container_2 = document.getElementById('debug-line-container-2');
        let focused = false;
        for (let l of data['lines'])
        {
            let line = new TextLine(l.id, l.annotated, l.text, l.np_confidences, l.ligatures_mapping, l.arabic, l.for_training,
                                    debug_line_container, debug_line_container_2, l.category, image_id)
            line.np_points = l.np_points;
            line.np_heights = l.np_heights;
            line.focus = false;
            this.add_line_to_map(i, line);
            this.lines.push(line);
            if (l.id == this.focus_to){
                line.focus = true;
                this.line_focus(line);
                this.polygon_click(line);
                focused = true;
            }
            observer.observe(line.container, {attributes: true});
            i += 1;
        }
        this.worst_confidence = 0.95;
        for(let l of this.lines){
            this.worst_confidence = Math.min(this.worst_confidence, l.line_confidence);
        }
        for(let l of this.lines){
            this.set_line_style(l, false);
        }

        if (this.focus_to != null){
            this.focus_to = null;
        }
        else{
            this.map_element.focus();
        }
    }

    add_line_to_map(i, line)
    {
        let points = [];

        for (let point of line.np_points)
        {
            points.push(xy(point[0], -point[1]));
        }
        line.polygon = L.polygon(points);

        line.polygon.addTo(this.map);
        line.polygon.on('click', this.polygon_click.bind(this, line));

        line.container.setAttribute("id", i);

        line.container.addEventListener('click', this.line_focus.bind(this, line));
        line.container.addEventListener('focusout', this.line_focus_out.bind(this, line));

        this.text_container.appendChild(line.container);
    }

    line_focus_from_checkbox(line) {
        this.line_focus(line);
        line.container.focus();
    }

    ignore_action_from_checkbox(line) {
        this.line_focus_from_checkbox(line);
        this.ignore_line_btn_action();
    }

    press_text_container(e)
    {
        if (e.keyCode == 13)
        {
            let line_number = parseInt(this.active_line.container.getAttribute("id"), 10);
            document.getElementById((line_number + 1).toString()).focus();
        }
    }

    polygon_click(line)
    {
        line.container.click();
    }

    line_focus(line)
    {
        if (this.active_line)
        {
            this.active_line.focus = false;
            this.set_line_style(this.active_line);
        }

        let focus_line_points = get_focus_line_points(line);
        this.map.stop();
        this.map.flyToBounds([xy(focus_line_points[0], -focus_line_points[2]), xy(focus_line_points[1], -focus_line_points[2])],
                             {animate: true, duration: 0.5});
        this.active_line = line;
        line.focus = true;
        this.set_line_style(line)

        this.swap_delete_line_button_blueprint();
        this.swap_ignore_line_button_blueprint();

        // this.change_url(this.active_line.id);
    }

    line_focus_out(line)
    {
        this.set_line_style(line)
    }

    show_line_change()
    {
        if (this.active_line)
        {
            let focus_line_points = get_focus_line_points(this.active_line);
            this.map.stop();
            this.map.flyToBounds([xy(focus_line_points[0], -focus_line_points[2]), xy(focus_line_points[1], -focus_line_points[2])],
                                 {animate: false, duration: 0});
        }
    }

    show_next_line()
    {
        var focused = false;
        if (this.active_line.id == undefined){
            for (let line of this.lines){
                if (Math.min.apply(Math, line.confidences) < 0.8 && line.text_line_element.style.backgroundColor != 'rgb(208, 255, 207)') {
                    this.line_focus(line);
                    this.polygon_click(line);
                    focused = true;
                    break;
                }

                if (focused){
                    break;
                }
            }
        }
        else {
            let index = this.lines.findIndex(x => x.id === this.active_line.id);
            let rest_of_lines = this.lines.slice(index+1);
            if (rest_of_lines.length != 0){
                for (let line of rest_of_lines) {
                    if (Math.min.apply(Math, line.confidences) < 0.8 && line.container.style.backgroundColor != 'rgb(208, 255, 207)') {
                        this.line_focus(line);
                        this.polygon_click(line);
                        focused = true;
                        break;
                    }

                    if (focused) {
                        break;
                    }
                }
            }
            else{
                next_page();
            }
        }
    }

    save_annotations()
    {
        for (let l of this.lines)
        {
            if (l.edited)
            {
                l.save();
            }
        }
    }

    compute_scores(){
        let route_ = Flask.url_for('document.compute_scores', {'document_id': document.querySelector('#document-id').textContent});
        $.get(route_);
    }
}


// HELPER FUNCTIONS
// #############################################################################

function get_focus_line_points(line)
{
    visual_categories = ["image", "photo", "graph", "initial", "map", "stamp", "code", "schema", "other"]

    let show_line_height = visual_categories.includes(line.category) ? 300 : 50;
    let show_bottom_pad = 100
    let width_boundary = get_line_width_boundary(line);
    let height_boundary = get_line_height_boundary(line);
    let start_x = width_boundary[0];
    let end_x = width_boundary[1];
    let start_y = height_boundary[0];
    let end_y = height_boundary[1];
    let line_height = line.np_heights[0] + line.np_heights[1];
    let y = start_y + line_height;
    let line_width = end_x - start_x;
    let container = $('.editor-map');
    let container_width = container.width();
    let container_height = container.height();
    let expected_show_line_height = line_height * (container_width / line_width);
    let new_line_width = (line_height * container_width) / show_line_height;
    if (expected_show_line_height > show_line_height)
    {
        start_x -= (new_line_width - line_width) / 2;
        end_x += (new_line_width - line_width) / 2;
    }
    if (expected_show_line_height < show_line_height)
    {
        end_x -= line_width - new_line_width;
    }
    let show_height_offset = (container_height / 2) - show_bottom_pad;
    let height_offset = (show_height_offset / (container_width / new_line_width));
    return [start_x, end_x, y - height_offset];
}

function get_line_height_boundary(line)
{
    let height_min = 100000000000000000000000;
    let height_max = 0;
    for (let coord of line.np_points)
    {
        if (coord[1] < height_min)
        {
            height_min = coord[1];
        }
        if (coord[1] > height_max)
        {
            height_max = coord[1];
        }
    }
    return [height_min, height_max];
}

function get_line_width_boundary(line)
{
    let width_min = 100000000000000000000000;
    let width_max = 0;
    for (let coord of line.np_points)
    {
        if (coord[0] < width_min)
        {
            width_min = coord[0];
        }
        if (coord[0] > width_max)
        {
            width_max = coord[0];
        }
    }
    return [width_min, width_max];
}

function componentToHex(c) {
    let hex = c.toString(16);
    return hex.length == 1 ? "0" + hex : hex;
}

function rgbToHex(r, g, b) {
    return "#" + componentToHex(r) + componentToHex(g) + componentToHex(b);
}




function scrollToElm(container, elm, duration){
    var pos = getRelativePos(container, elm);
    scrollTo( container, pos.top , duration);  // duration in seconds
}

function getRelativePos(container, elm){
    var pPos = container.getBoundingClientRect(); // parent pos
    var cPos = elm.getBoundingClientRect(); // target pos
    var pos = {};

    pos.top    = cPos.top    - pPos.top + elm.parentNode.scrollTop,
    pos.right  = cPos.right  - pPos.right,
    pos.bottom = cPos.bottom - pPos.bottom,
    pos.left   = cPos.left   - pPos.left;

    return pos;
}

function scrollTo(element, to, duration, onDone) {
    var start = element.scrollTop,
    change = to - start,
    startTime = performance.now(),
    val, now, elapsed, t;

    function animateScroll(){
        now = performance.now();
        elapsed = (now - startTime)/1000;
        t = (elapsed/duration);

        element.scrollTop = start + change * easeInOutQuad(t);

        if( t < 1 )
            window.requestAnimationFrame(animateScroll);
        else
            onDone && onDone();
    };

    animateScroll();
}

function easeInOutQuad(t){ return t<.5 ? 2*t*t : -1+(4-2*t)*t };



// #############################################################################