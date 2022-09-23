class Controller {
    constructor() {
    }

    setCallbacks() {
        this.setForwardCallbacks();
        this.setBackwardCallbacks();
        this.setStartCallbacks();
    }

    setForwardCallbacks() {
        document.querySelectorAll('[data-app-controls-forward]').forEach(element =>
            element.addEventListener("click", { handleEvent: this.goForwardEventHandler, controller: this }, false)
        );
    }

    setBackwardCallbacks() {
        document.querySelectorAll('[data-app-controls-back]').forEach(element =>
            element.addEventListener("click", { handleEvent: this.goBackwardEventHandler, controller: this }, false)
        );
    }

    setStartCallbacks() {
        document.querySelectorAll('[data-app-controls-start]').forEach(element =>
            element.addEventListener("click", { handleEvent: this.goStartEventHandler, controller: this }, false)
        );
    }

    goForwardEventHandler(e) {
        this.controller.currentPage += 1;
        this.controller.showCurrentPage();
    }

    goBackwardEventHandler(e) {
        this.controller.currentPage -= 1;
        this.controller.showCurrentPage();
    }

    goStartEventHandler(e) {
        window.location = '/';
        this.controller.currentPage = 0;
        this.controller.showCurrentPage();
    }

    goForward() {
        this.currentPage += 1;
        this.showCurrentPage();
    }

    goBackward() {
        this.currentPage -= 1;
        this.showCurrentPage();
    }

    goStart() {
        window.location = '/';
        this.currentPage = 0;
        this.showCurrentPage();
    }

    showCurrentPage() {
        document.querySelectorAll('[data-app-page]').forEach(element => {
                if (this.currentPage == element.getAttribute("data-app-page")) {
                    element.classList.remove("app-page-hidden");
                    let onShowCallback = element.getAttribute("data-on-show");
                    if (onShowCallback) {
                        window[onShowCallback]();
                    }
                }
                else if (!element.classList.contains("app-page-hidden")) {
                    element.classList.add("app-page-hidden");
                    let onHideCallback = element.getAttribute("data-on-hide");
                    if (onHideCallback) {
                        window[onHideCallback]();
                    }
                }
            });
    }
    
    startApp() {
        this.currentPage = 0;
        this.setCallbacks();

        let appElement = document.getElementById('app');
        let onLoadCallback = appElement.getAttribute("data-on-load");
        if (onLoadCallback) {
            window[onLoadCallback]();
        }

        this.showCurrentPage();
    }
}
