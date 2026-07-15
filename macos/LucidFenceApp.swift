import AppKit
import Darwin
import Foundation
import WebKit

enum PortState {
    case lucidFence
    case occupied
    case free
}

private struct HealthResponse: Decodable {
    let status: String
    let service: String
    let desktopNonce: String?

    enum CodingKeys: String, CodingKey {
        case status, service
        case desktopNonce = "desktop_nonce"
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var backendProcess: Process?
    private var backendLog: FileHandle?
    private var selectedPort = 8765
    private var pollAttempt = 0
    private var backendReady = false
    private var isTerminating = false
    private var hasShownFatalError = false
    private let desktopNonce = UUID().uuidString + UUID().uuidString
    private(set) var startedBackend = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        configureMenu()
        configureWindow()
        showStartupPage(message: "Preparando tu espacio local…")
        selectPort(8765)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func configureWindow() {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        let environment = ProcessInfo.processInfo.environment
        configuration.preferences.setValue(environment["LUCIDFENCE_QA_SNAPSHOT"] != nil,
                                           forKey: "developerExtrasEnabled")

        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.setValue(false, forKey: "drawsBackground")

        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1360, height: 860),
            styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
            backing: .buffered,
            defer: false
        )
        window.title = "LucidFence"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.minSize = NSSize(width: 1040, height: 680)
        window.collectionBehavior = [.moveToActiveSpace, .fullScreenPrimary]
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.contentView = webView
        window.center()
        window.makeKeyAndOrderFront(nil)
        window.orderFrontRegardless()
    }

    private func configureMenu() {
        let mainMenu = NSMenu()

        let appItem = NSMenuItem()
        mainMenu.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Acerca de LucidFence", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Abrir en el navegador", action: #selector(openInBrowser), keyEquivalent: "b")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "Ocultar LucidFence", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Salir de LucidFence", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu

        let viewItem = NSMenuItem()
        mainMenu.addItem(viewItem)
        let viewMenu = NSMenu(title: "Visualización")
        viewMenu.addItem(withTitle: "Recargar", action: #selector(reloadPage), keyEquivalent: "r")
        viewMenu.addItem(NSMenuItem.separator())
        viewMenu.addItem(withTitle: "Pantalla completa", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        viewItem.submenu = viewMenu

        NSApp.mainMenu = mainMenu
    }

    private func selectPort(_ candidate: Int) {
        guard candidate <= 8775 else {
            showFatalError("No hay un puerto local disponible entre 8765 y 8775.")
            return
        }
        inspectPort(candidate, expectedNonce: nil) { [weak self] state in
            guard let self = self else { return }
            DispatchQueue.main.async {
                switch state {
                case .lucidFence:
                    self.selectPort(candidate + 1)
                case .free:
                    self.selectedPort = candidate
                    self.startEmbeddedBackend()
                case .occupied:
                    self.selectPort(candidate + 1)
                }
            }
        }
    }

    private func inspectPort(_ port: Int, expectedNonce: String?, completion: @escaping (PortState) -> Void) {
        guard let url = URL(string: "http://127.0.0.1:\(port)/api/health") else {
            completion(.occupied)
            return
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 0.45
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let urlError = error as? URLError {
                completion(urlError.code == .cannotConnectToHost ? .free : .occupied)
                return
            }
            let health = try? JSONDecoder().decode(HealthResponse.self, from: data ?? Data())
            if let http = response as? HTTPURLResponse, http.statusCode == 200,
               let health = health, health.service == "lucidfence", health.status == "ok",
               let expectedNonce = expectedNonce, health.desktopNonce == expectedNonce {
                completion(.lucidFence)
            } else {
                completion(.occupied)
            }
        }.resume()
    }

    private func startEmbeddedBackend() {
        guard let resources = Bundle.main.resourceURL else {
            showFatalError("No se encuentran los recursos de la aplicación.")
            return
        }
        let executable = resources.appendingPathComponent("backend/LucidFenceBackend")
        guard FileManager.default.isExecutableFile(atPath: executable.path) else {
            showFatalError("La instalación está incompleta: falta el motor local.")
            return
        }

        let logs = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Logs/LucidFence", isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
            try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: logs.path)
            let logURL = logs.appendingPathComponent("desktop-backend.log")
            let backupURL = logs.appendingPathComponent("desktop-backend.log.1")
            let size = (try? FileManager.default.attributesOfItem(atPath: logURL.path)[.size] as? NSNumber)?.intValue ?? 0
            if size > 5 * 1024 * 1024 {
                try? FileManager.default.removeItem(at: backupURL)
                try FileManager.default.moveItem(at: logURL, to: backupURL)
            }
            if !FileManager.default.fileExists(atPath: logURL.path) {
                FileManager.default.createFile(atPath: logURL.path, contents: nil)
            }
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: logURL.path)
            backendLog = try FileHandle(forWritingTo: logURL)
            try backendLog?.seekToEnd()
        } catch {
            showFatalError("No se pudo preparar el log local: \(error.localizedDescription)")
            return
        }

        let process = Process()
        process.executableURL = executable
        process.currentDirectoryURL = resources.appendingPathComponent("backend", isDirectory: true)
        let parentEnvironment = ProcessInfo.processInfo.environment
        var environment = [
            "LUCIDFENCE_HOST": "127.0.0.1",
            "LUCIDFENCE_PORT": String(selectedPort),
            "LUCIDFENCE_DESKTOP_NONCE": desktopNonce,
            "LUCIDFENCE_PARENT_PID": String(ProcessInfo.processInfo.processIdentifier),
            "LUCIDFENCE_CONFIG_FILE": "config.desktop.json",
            "PYTHONUNBUFFERED": "1",
            "HOME": FileManager.default.homeDirectoryForCurrentUser.path,
            "TMPDIR": NSTemporaryDirectory(),
        ]
        for key in ["LANG", "LC_ALL"] {
            if let value = parentEnvironment[key] { environment[key] = value }
        }
        process.environment = environment
        process.standardOutput = backendLog
        process.standardError = backendLog
        process.terminationHandler = { [weak self] task in
            guard let self = self, !self.isTerminating else { return }
            DispatchQueue.main.async {
                self.backendReady = false
                self.showFatalError("El motor local terminó inesperadamente (código \(task.terminationStatus)).")
            }
        }

        do {
            try process.run()
            backendProcess = process
            startedBackend = true
            pollAttempt = 0
            waitForBackend()
        } catch {
            showFatalError("No se pudo iniciar el motor local: \(error.localizedDescription)")
        }
    }

    private func waitForBackend() {
        inspectPort(selectedPort, expectedNonce: desktopNonce) { [weak self] state in
            guard let self = self else { return }
            DispatchQueue.main.async {
                if state == .lucidFence {
                    self.backendReady = true
                    self.loadApplication()
                    return
                }
                self.pollAttempt += 1
                if self.pollAttempt >= 120 || self.backendProcess?.isRunning == false {
                    self.showFatalError("LucidFence no pudo iniciar su motor local. Revisa ~/Library/Logs/LucidFence/desktop-backend.log")
                    return
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                    self.waitForBackend()
                }
            }
        }
    }

    private func loadApplication() {
        guard let url = URL(string: "http://127.0.0.1:\(selectedPort)/app/") else { return }
        webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 30))
    }

    private func showStartupPage(message: String) {
        let html = """
        <!doctype html><html><head><meta charset="utf-8"><style>
        html,body{height:100%;margin:0;background:#090d12;color:#e8edf3;font-family:-apple-system,BlinkMacSystemFont,sans-serif}
        body{display:grid;place-items:center}.box{text-align:center}.mark{width:72px;height:72px;margin:auto;border-radius:19px;background:linear-gradient(145deg,#806cff,#5364e9);display:grid;place-items:center;box-shadow:0 18px 50px #5364e944;font-size:34px}.name{font-size:26px;font-weight:700;margin-top:22px}.msg{color:#8d98a8;margin-top:8px;font-size:14px}.pulse{display:inline-block;width:7px;height:7px;border-radius:50%;background:#59d89c;margin-right:8px;animation:p 1.2s infinite}@keyframes p{50%{opacity:.25}}
        </style></head><body><div class="box"><div class="mark">⌾</div><div class="name">LucidFence</div><div class="msg"><span class="pulse"></span>\(message)</div></div></body></html>
        """
        webView.loadHTMLString(html, baseURL: nil)
    }

    private func showFatalError(_ message: String) {
        guard !hasShownFatalError else { return }
        hasShownFatalError = true
        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = "LucidFence no pudo abrirse"
        alert.informativeText = message
        alert.addButton(withTitle: "Cerrar")
        alert.runModal()
        NSApp.terminate(nil)
    }

    @objc private func reloadPage() {
        if backendReady { loadApplication() }
    }

    @objc private func openInBrowser() {
        guard backendReady else { return }
        if let url = URL(string: "http://127.0.0.1:\(selectedPort)/app/") {
            NSWorkspace.shared.open(url)
        }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction,
                 windowFeatures: WKWindowFeatures) -> WKWebView? {
        guard navigationAction.targetFrame == nil,
              let url = navigationAction.request.url else { return nil }
        if url.scheme == "http" || url.scheme == "https" {
            NSWorkspace.shared.open(url)
        }
        return nil
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if !isTerminating { showFatalError("No se pudo cargar la interfaz local: \(error.localizedDescription)") }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        if !isTerminating { showFatalError("La interfaz local dejó de responder: \(error.localizedDescription)") }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.cancel)
            return
        }
        if url.scheme == "about" {
            decisionHandler(.allow)
        } else if url.scheme == "http", url.host == "127.0.0.1",
                  (url.port ?? 80) == selectedPort {
            decisionHandler(.allow)
        } else if navigationAction.navigationType == .linkActivated,
                  url.scheme == "https" || url.scheme == "http" {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
        } else {
            decisionHandler(.cancel)
        }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard let path = ProcessInfo.processInfo.environment["LUCIDFENCE_QA_SNAPSHOT"],
              !path.isEmpty,
              webView.url?.host == "127.0.0.1" else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            let configuration = WKSnapshotConfiguration()
            configuration.rect = webView.bounds
            webView.takeSnapshot(with: configuration) { image, _ in
                guard let tiff = image?.tiffRepresentation,
                      let bitmap = NSBitmapImageRep(data: tiff),
                      let png = bitmap.representation(using: .png, properties: [:]) else { return }
                try? png.write(to: URL(fileURLWithPath: path), options: .atomic)
            }
        }
    }

    func windowWillClose(_ notification: Notification) {
        NSApp.terminate(nil)
    }

    func applicationWillTerminate(_ notification: Notification) {
        isTerminating = true
        if startedBackend, let process = backendProcess, process.isRunning {
            process.terminate()
            let deadline = Date().addingTimeInterval(1.5)
            while process.isRunning && Date() < deadline {
                usleep(50_000)
            }
            if process.isRunning {
                Darwin.kill(process.processIdentifier, SIGKILL)
            }
        }
        try? backendLog?.close()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        window.orderFrontRegardless()
        NSApp.activate(ignoringOtherApps: true)
        return true
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
