function importJetzt(button) {
    button.disabled = true;
    var originalText = button.textContent;
    button.textContent = "Import laeuft...";

    fetch("/import/jetzt", { method: "POST" })
        .then(function (response) {
            if (!response.ok) {
                throw new Error("Import fehlgeschlagen (HTTP " + response.status + ")");
            }
            return response.json();
        })
        .then(function () {
            window.location.reload();
        })
        .catch(function (err) {
            button.disabled = false;
            button.textContent = originalText;
            alert("Import konnte nicht gestartet werden: " + err.message);
        });
}

document.addEventListener("DOMContentLoaded", function () {
    var importButton = document.getElementById("import-jetzt-button");
    if (importButton) {
        importButton.addEventListener("click", function () {
            importJetzt(importButton);
        });
    }

    if (document.body.dataset.autoprint === "true") {
        window.print();
    }
});
