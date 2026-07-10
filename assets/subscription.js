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
            {
                name: "Happ",
                url: "https://apps.apple.com/search?term=happ%20proxy",
                steps: [
                    "Install Happ using the button below.",
                    'Open Happ and tap the "+" button in the top right.',
                    'Copy your link above, then tap "Add from clipboard".',
                    "Tap the server that appears and press the big Connect button."
                ]
            },
            {
                name: "v2RayTun",
                url: "https://apps.apple.com/search?term=v2raytun",
                steps: [
                    "Install v2RayTun using the button below.",
                    'Open the app and tap the "+" icon.',
                    'Copy your link above, then choose "Import from clipboard".',
                    "Select the server and tap the Connect button."
                ]
            },
            {
                name: "FlClashX",
                url: "https://apps.apple.com/search?term=flclash",
                steps: [
                    "Install FlClash using the button below.",
                    'Open the app, go to "Profiles" and tap "+".',
                    'Copy your link above, then choose "Import from clipboard" (or paste the URL directly).',
                    "Select the profile and toggle the connection switch."
                ]
            },
            {
                name: "Clash Mi",
                url: "https://apps.apple.com/search?term=clash%20mi",
                steps: [
                    "Install Clash Mi using the button below.",
                    'Open the app and go to the "Profiles" tab.',
                    'Tap "+" and choose "Import from clipboard" after copying your link above.',
                    "Select the profile and turn on the VPN toggle."
                ]
            },
            {
                name: "Shadowrocket",
                url: "https://apps.apple.com/search?term=shadowrocket",
                steps: [
                    "Install Shadowrocket using the button below (paid app).",
                    'Open the app and tap the "+" in the top right.',
                    'Copy your link above, then tap "Add from clipboard" (or tap Type and paste manually).',
                    "Tap the server and toggle the switch at the top to connect."
                ]
            }
        ]
    },
    windows: {
        apps: [
            {
                name: "v2rayN",
                url: "https://github.com/2dust/v2rayN/releases",
                steps: [
                    "Download and extract v2rayN using the button below (no installer needed, just unzip and run).",
                    'Copy your link above, then go to Servers → "Import bulk URL from clipboard".',
                    "Select the server in the list and right-click it, then choose \"Set as active server\".",
                    "Enable the system proxy from the tray icon to start routing traffic."
                ]
            },
            {
                name: "NekoRay",
                url: "https://github.com/MatsuriDayo/nekoray/releases",
                steps: [
                    "Download and install NekoRay using the button below.",
                    'Copy your link above, then go to Program → "Add profile from clipboard".',
                    'Select the profile, right-click it and choose "Start".',
                    "Enable the system proxy option if you want all apps routed automatically."
                ]
            },
            {
                name: "Clash Verge Rev",
                url: "https://github.com/clash-verge-rev/clash-verge-rev/releases",
                steps: [
                    "Download and install Clash Verge Rev using the button below.",
                    'Open the app and go to the "Profiles" tab.',
                    'Click "Import", paste your link from above, and confirm.',
                    'Select the profile and enable the "System Proxy" toggle.'
                ]
            }
        ]
    },
    macos: {
        apps: [
            {
                name: "V2Box",
                url: "https://apps.apple.com/search?term=v2box",
                steps: [
                    "Install V2Box using the button below.",
                    'Open the app and tap the "+" button to add a new configuration.',
                    'Copy your link above, then choose "Import from clipboard".',
                    "Select the server and tap Connect."
                ]
            },
            {
                name: "NekoRay",
                url: "https://github.com/MatsuriDayo/nekoray/releases",
                steps: [
                    "Download NekoRay using the button below and move it to your Applications folder.",
                    'Copy your link above, then go to Program → "Add profile from clipboard".',
                    'Select the profile, right-click it and choose "Start".',
                    "Enable the system proxy option if you want all apps routed automatically."
                ]
            },
            {
                name: "Clash Verge Rev",
                url: "https://github.com/clash-verge-rev/clash-verge-rev/releases",
                steps: [
                    "Download and install Clash Verge Rev using the button below.",
                    'Open the app and go to the "Profiles" tab.',
                    'Click "Import", paste your link from above, and confirm.',
                    'Select the profile and enable the "System Proxy" toggle.'
                ]
            }
        ]
    },
    linux: {
        apps: [
            {
                name: "NekoRay",
                url: "https://github.com/MatsuriDayo/nekoray/releases",
                steps: [
                    "Download the AppImage (or archive for your distro) using the button below.",
                    "Make it executable (chmod +x) and run it.",
                    'Copy your link above, then go to Program → "Add profile from clipboard".',
                    'Select the profile, right-click it and choose "Start".'
                ]
            },
            {
                name: "Clash Verge Rev",
                url: "https://github.com/clash-verge-rev/clash-verge-rev/releases",
                steps: [
                    "Download the package for your distro (.deb/.rpm/AppImage) using the button below.",
                    'Open the app and go to the "Profiles" tab.',
                    'Click "Import", paste your link from above, and confirm.',
                    'Select the profile and enable the "System Proxy" toggle.'
                ]
            }
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
