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

function initProgressBars() {
    document.querySelectorAll(".progress-fill[data-percent]").forEach((bar) => {
        bar.style.width = bar.dataset.percent + "%";
    });
}

const INSTALL_GUIDES = {
    android: {
        steps: [
            "Install one of the apps below on your device.",
            'Open the app and tap "+" to add a new profile.',
            'Copy your link above, then choose "Import from Clipboard" (or paste it manually).',
            "Select the server in the list and tap Connect."
        ],
        apps: [
            { name: "Happ", url: "https://play.google.com/store/search?q=happ+proxy&c=apps" },
            { name: "v2RayTun", url: "https://play.google.com/store/search?q=v2raytun&c=apps" },
            { name: "FlClashX", url: "https://play.google.com/store/search?q=flclash&c=apps" }
        ]
    },
    ios: {
        steps: [
            "Install one of the apps below from the App Store.",
            'Open the app and tap "+" to add a new configuration.',
            "Paste your subscription link from above, or scan the QR code.",
            "Select the server and tap Connect."
        ],
        apps: [
            { name: "Happ", url: "https://apps.apple.com/search?term=happ%20proxy" },
            { name: "v2RayTun", url: "https://apps.apple.com/search?term=v2raytun" },
            { name: "FlClashX", url: "https://apps.apple.com/search?term=flclash" },
            { name: "Clash Mi", url: "https://apps.apple.com/search?term=clash%20mi" },
            { name: "Shadowrocket", url: "https://apps.apple.com/search?term=shadowrocket" }
        ]
    }
};

function renderInstallGuide(platform) {
    const guide = INSTALL_GUIDES[platform];
    const stepsEl = document.getElementById("installSteps");
    const appsEl = document.getElementById("installApps");
    if (!guide || !stepsEl || !appsEl) return;

    stepsEl.innerHTML = "";
    guide.steps.forEach((step) => {
        const li = document.createElement("li");
        li.textContent = step;
        stepsEl.appendChild(li);
    });

    appsEl.innerHTML = "";
    guide.apps.forEach((app) => {
        const a = document.createElement("a");
        a.className = "chip";
        a.href = app.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = app.name;
        appsEl.appendChild(a);
    });
}

function initInstallGuide() {
    const select = document.getElementById("platformSelect");
    if (!select) return;
    renderInstallGuide(select.value);
    select.addEventListener("change", () => renderInstallGuide(select.value));
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

document.addEventListener("DOMContentLoaded", () => {
    initProgressBars();
    initSubscriptionPage();
    initInstallGuide();
});
