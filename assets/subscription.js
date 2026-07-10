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

// Generic fallback steps for platforms that don't (yet) have per-app
// instructions - every app on that platform shares this same text.
const GENERIC_DESKTOP_STEPS = [
    "Download and install one of the apps below.",
    "Open the app and find its subscription/profile settings.",
    "Add a new subscription using your link from above (or import from clipboard).",
    "Select the server in the list and connect."
];

const INSTALL_GUIDES = {
    android: {
        apps: [
            {
                name: "Happ",
                url: "https://play.google.com/store/search?q=happ+proxy&c=apps",
                steps: [
                    "Install Happ using the button below.",
                    'Open Happ and tap the "+" button in the top right.',
                    'Copy your link above, then tap "Add from clipboard".',
                    "Tap the server that appears and press the big Connect button."
                ]
            },
            {
                name: "v2RayTun",
                url: "https://play.google.com/store/search?q=v2raytun&c=apps",
                steps: [
                    "Install v2RayTun using the button below.",
                    'Open the app and tap the "+" icon.',
                    'Copy your link above, then choose "Import from clipboard".',
                    "Select the server and tap the Connect button."
                ]
            },
            {
                name: "FlClashX",
                url: "https://play.google.com/store/search?q=flclash&c=apps",
                steps: [
                    "Install FlClash using the button below.",
                    'Open the app, go to "Profiles" and tap "+".',
                    "Copy your link above, then choose \"Import from clipboard\" (or paste the URL directly).",
                    "Select the profile and toggle the connection switch."
                ]
            }
        ]
    },
    ios: {
        apps: [
            { name: "Happ", url: "https://apps.apple.com/search?term=happ%20proxy", steps: GENERIC_DESKTOP_STEPS },
            { name: "v2RayTun", url: "https://apps.apple.com/search?term=v2raytun", steps: GENERIC_DESKTOP_STEPS },
            { name: "FlClashX", url: "https://apps.apple.com/search?term=flclash", steps: GENERIC_DESKTOP_STEPS },
            { name: "Clash Mi", url: "https://apps.apple.com/search?term=clash%20mi", steps: GENERIC_DESKTOP_STEPS },
            { name: "Shadowrocket", url: "https://apps.apple.com/search?term=shadowrocket", steps: GENERIC_DESKTOP_STEPS }
        ]
    },
    windows: {
        apps: [
            { name: "v2rayN", url: "https://github.com/2dust/v2rayN/releases", steps: GENERIC_DESKTOP_STEPS },
            { name: "NekoRay", url: "https://github.com/MatsuriDayo/nekoray/releases", steps: GENERIC_DESKTOP_STEPS },
            { name: "Clash Verge Rev", url: "https://github.com/clash-verge-rev/clash-verge-rev/releases", steps: GENERIC_DESKTOP_STEPS }
        ]
    },
    macos: {
        apps: [
            { name: "V2Box", url: "https://apps.apple.com/search?term=v2box", steps: GENERIC_DESKTOP_STEPS },
            { name: "NekoRay", url: "https://github.com/MatsuriDayo/nekoray/releases", steps: GENERIC_DESKTOP_STEPS },
            { name: "Clash Verge Rev", url: "https://github.com/clash-verge-rev/clash-verge-rev/releases", steps: GENERIC_DESKTOP_STEPS }
        ]
    },
    linux: {
        apps: [
            { name: "NekoRay", url: "https://github.com/MatsuriDayo/nekoray/releases", steps: GENERIC_DESKTOP_STEPS },
            { name: "Clash Verge Rev", url: "https://github.com/clash-verge-rev/clash-verge-rev/releases", steps: GENERIC_DESKTOP_STEPS }
        ]
    }
};

function renderInstallSteps(app) {
    const stepsEl = document.getElementById("installSteps");
    const downloadBtn = document.getElementById("installDownloadBtn");
    if (!stepsEl) return;

    stepsEl.innerHTML = "";
    app.steps.forEach((step) => {
        const li = document.createElement("li");
        li.textContent = step;
        stepsEl.appendChild(li);
    });

    if (downloadBtn) {
        downloadBtn.href = app.url;
        downloadBtn.textContent = "Get " + app.name + " ↗";
        downloadBtn.style.display = "inline-block";
    }
}

function renderInstallGuide(platform) {
    const guide = INSTALL_GUIDES[platform];
    const appsEl = document.getElementById("installApps");
    if (!guide || !appsEl) return;

    appsEl.innerHTML = "";
    guide.apps.forEach((app, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "chip app-tab" + (index === 0 ? " active" : "");
        button.textContent = app.name;
        button.addEventListener("click", () => {
            appsEl.querySelectorAll(".app-tab").forEach((el) => el.classList.remove("active"));
            button.classList.add("active");
            renderInstallSteps(app);
        });
        appsEl.appendChild(button);
    });

    renderInstallSteps(guide.apps[0]);
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
