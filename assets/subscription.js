function readLinksData() {
    const el = document.getElementById("subscription-data");
    if (!el) return [];
    try {
        return JSON.parse(el.textContent);
    } catch (e) {
        console.error("Failed to parse subscription data", e);
        return [];
    }
}

function copyToClipboard(text, button) {
    const tempInput = document.createElement("input");
    tempInput.setAttribute("value", text);
    document.body.appendChild(tempInput);
    tempInput.select();
    document.execCommand("copy");
    document.body.removeChild(tempInput);

    const original = button.textContent;
    button.textContent = "Copied!";
    setTimeout(function () {
        button.textContent = original;
    }, 1500);
}

function initProtocolTabs(links, onSelect) {
    const tabs = document.querySelectorAll(".proto-tab");
    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            tabs.forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");
            onSelect(links[parseInt(tab.dataset.index, 10)]);
        });
    });
}

function initCopyButton(getActiveLink) {
    const copyBtn = document.getElementById("copyBtn");
    if (!copyBtn) return;
    copyBtn.addEventListener("click", () => copyToClipboard(getActiveLink(), copyBtn));
}

function initQrPopup(getActiveLink) {
    const qrBtn = document.getElementById("qrBtn");
    const qrPopup = document.getElementById("qrPopup");
    const qrCloseBtn = document.getElementById("qrCloseBtn");
    const qrCodeContainer = document.getElementById("qrCodeContainer");
    if (!qrBtn || !qrPopup || !qrCodeContainer) return;

    qrBtn.addEventListener("click", () => {
        while (qrCodeContainer.firstChild) {
            qrCodeContainer.removeChild(qrCodeContainer.firstChild);
        }
        new QRCode(qrCodeContainer, {
            text: getActiveLink(),
            width: 220,
            height: 220,
            correctLevel: QRCode.CorrectLevel.L
        });
        qrPopup.style.display = "block";
    });

    if (qrCloseBtn) {
        qrCloseBtn.addEventListener("click", () => {
            qrPopup.style.display = "none";
        });
    }
}

function initSubscriptionPage() {
    const links = readLinksData();
    if (links.length === 0) return;

    let activeLink = links[0];
    const linkEl = document.getElementById("activeLink");

    function setActiveLink(link) {
        activeLink = link;
        if (linkEl) linkEl.textContent = link;
    }

    initProtocolTabs(links, setActiveLink);
    initCopyButton(() => activeLink);
    initQrPopup(() => activeLink);
}

document.addEventListener("DOMContentLoaded", initSubscriptionPage);
