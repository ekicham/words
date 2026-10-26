import AppKit
import WebKit
import UniformTypeIdentifiers

final class WordIsle: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
    var window: NSWindow!
    var webView: WKWebView!
    var backend: Process?
    var readinessTimer: Timer?
    var readyFile: URL!
    var baseURL: URL?
    var quitting = false
    let files = FileManager.default
    lazy var dataDirectory: URL = {
        if let path = ProcessInfo.processInfo.environment["WORD_ISLE_DATA_DIR"] {
            return URL(fileURLWithPath: path, isDirectory: true)
        }
        return files.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("WordIsle", isDirectory: true)
    }()

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let other = NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "net.wordisle.desktop")
            .first(where: { $0.processIdentifier != getpid() }) {
            other.activate(options: [.activateIgnoringOtherApps])
            NSApp.terminate(nil)
            return
        }
        makeMenus()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1180, height: 800),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "词屿 Word Isle"
        window.minSize = NSSize(width: 820, height: 600)
        window.setFrameAutosaveName("WordIsleWindow")
        window.center()
        window.isReleasedWhenClosed = false
        let configuration = WKWebViewConfiguration()
        configuration.mediaTypesRequiringUserActionForPlayback = []
        configuration.preferences.isElementFullscreenEnabled = true
        configuration.userContentController.add(self, name: "preferences")
        configuration.userContentController.add(self, name: "download")
        let preferences = UserDefaults.standard.dictionary(forKey: "learningPreferences") ?? [:]
        let json = (try? JSONSerialization.data(withJSONObject: preferences)) ?? Data("{}".utf8)
        configuration.userContentController.addUserScript(WKUserScript(
            source: "window.wordIsleDesktop = {preferences: \(String(decoding: json, as: UTF8.self))};",
            injectionTime: .atDocumentStart, forMainFrameOnly: true))
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        window.contentView = webView
        webView.loadHTMLString("<meta charset='utf-8'><body style='font:24px system-ui;padding:60px'>正在打开词屿…</body>", baseURL: nil)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        startBackend()
    }

    func makeMenus() {
        let menu = NSMenu()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "关于词屿", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "隐藏词屿", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "退出词屿", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let appItem = NSMenuItem(); appItem.submenu = appMenu; menu.addItem(appItem)
        let edit = NSMenu(title: "编辑")
        for (title, selector, key) in [("撤销", "undo:", "z"), ("重做", "redo:", "Z"),
                                       ("剪切", "cut:", "x"), ("复制", "copy:", "c"),
                                       ("粘贴", "paste:", "v"), ("全选", "selectAll:", "a")] {
            edit.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key)
        }
        let editItem = NSMenuItem(); editItem.submenu = edit; menu.addItem(editItem)
        let view = NSMenu(title: "窗口")
        view.addItem(withTitle: "最小化", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        view.addItem(withTitle: "进入/退出全屏", action: #selector(NSWindow.toggleFullScreen(_:)), keyEquivalent: "f")
        view.items.last?.keyEquivalentModifierMask = [.command, .control]
        let viewItem = NSMenuItem(); viewItem.submenu = view; menu.addItem(viewItem)
        let help = NSMenu(title: "帮助")
        help.addItem(withTitle: "打开学习数据文件夹", action: #selector(openDataDirectory), keyEquivalent: "")
        help.addItem(withTitle: "安装与使用说明", action: #selector(openHelp), keyEquivalent: "")
        let helpItem = NSMenuItem(); helpItem.submenu = help; menu.addItem(helpItem)
        NSApp.mainMenu = menu
    }

    @objc func openDataDirectory() { NSWorkspace.shared.open(dataDirectory) }
    @objc func openHelp() {
        if let url = Bundle.main.url(forResource: "安装与使用说明", withExtension: "txt") { NSWorkspace.shared.open(url) }
    }

    func startBackend() {
        do {
            try files.createDirectory(at: dataDirectory, withIntermediateDirectories: true)
            let log = dataDirectory.appendingPathComponent("desktop.log")
            try Data().write(to: log)
            let output = try FileHandle(forWritingTo: log)
            defer { try? output.close() }
            readyFile = files.temporaryDirectory.appendingPathComponent("word-isle-\(UUID().uuidString).json")
            let process = Process()
            process.executableURL = Bundle.main.bundleURL.appendingPathComponent("Contents/Helpers/WordIsleBackend.app/Contents/MacOS/WordIsleBackend")
            process.arguments = ["--db", dataDirectory.appendingPathComponent("words.sqlite3").path,
                                 "--ready-file", readyFile.path, "--parent-pid", String(getpid())]
            var environment = ProcessInfo.processInfo.environment
            environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
            environment.removeValue(forKey: "PYTHONPATH")
            environment.removeValue(forKey: "PYTHONHOME")
            environment.removeValue(forKey: "DYLD_FRAMEWORK_PATH")
            environment.removeValue(forKey: "DYLD_LIBRARY_PATH")
            process.environment = environment
            process.standardOutput = output
            process.standardError = output
            process.terminationHandler = { [weak self] _ in
                DispatchQueue.main.async {
                    guard let self = self, !self.quitting else { return }
                    self.fail("本地服务已退出。学习记录已保存，请重新打开词屿。\n诊断日志：\(log.path)")
                }
            }
            backend = process
            try process.run()
            let deadline = Date().addingTimeInterval(30)
            readinessTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] timer in
                guard let self = self else { timer.invalidate(); return }
                if let data = try? Data(contentsOf: self.readyFile),
                   let status = try? JSONSerialization.jsonObject(with: data) as? [String: Int],
                   let port = status["port"], (1...65535).contains(port) {
                    timer.invalidate()
                    self.baseURL = URL(string: "http://127.0.0.1:\(port)")!
                    self.webView.load(URLRequest(url: self.baseURL!))
                } else if Date() > deadline {
                    timer.invalidate()
                    self.fail("启动超过 30 秒，请重新打开词屿。\n诊断日志：\(log.path)")
                }
            }
        } catch { fail("无法启动词屿：\(error.localizedDescription)") }
    }

    func fail(_ message: String) {
        guard !quitting else { return }
        quitting = true
        readinessTimer?.invalidate()
        let alert = NSAlert()
        alert.messageText = "词屿未能继续运行"
        alert.informativeText = message
        alert.addButton(withTitle: "退出")
        alert.runModal()
        NSApp.terminate(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil)
        return true
    }
    func applicationWillTerminate(_ notification: Notification) {
        quitting = true
        readinessTimer?.invalidate()
        if let process = backend, process.isRunning {
            process.terminate()
            process.waitUntilExit()
        }
        if let ready = readyFile { try? files.removeItem(at: ready) }
    }

    func isLocal(_ url: URL?) -> Bool {
        guard let url = url, let base = baseURL else { return false }
        return url.scheme == base.scheme && url.host == base.host && url.port == base.port
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if isLocal(action.request.url) || (baseURL == nil && action.request.url?.absoluteString == "about:blank") {
            decisionHandler(.allow)
        } else {
            if let url = action.request.url, ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
            decisionHandler(.cancel)
        }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url, ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
        return nil
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.json]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.beginSheetModal(for: window) { completionHandler($0 == .OK ? panel.urls : nil) }
    }
    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin,
                 initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType,
                 decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        // WebKit may leave frame.request.url empty here; validate the requesting origin instead.
        guard frame.isMainFrame, isLocal(webView.url), type == .microphone,
              origin.protocol == baseURL?.scheme, origin.host == baseURL?.host,
              origin.port == baseURL?.port else { decisionHandler(.deny); return }
        decisionHandler(.prompt)
    }
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let alert = NSAlert(); alert.messageText = message
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, isLocal(message.frameInfo.request.url),
              let body = message.body as? [String: Any], JSONSerialization.isValidJSONObject(body),
              let bytes = try? JSONSerialization.data(withJSONObject: body), bytes.count <= 10_000_000 else { return }
        if message.name == "preferences" {
            UserDefaults.standard.set(body, forKey: "learningPreferences")
        } else if message.name == "download", let name = body["name"] as? String, let text = body["text"] as? String {
            let panel = NSSavePanel()
            panel.nameFieldStringValue = (name as NSString).lastPathComponent
            panel.canCreateDirectories = true
            panel.beginSheetModal(for: window) { [weak self] result in
                guard result == .OK, let url = panel.url else { return }
                do { try text.write(to: url, atomically: true, encoding: .utf8) }
                catch {
                    guard let self = self else { return }
                    let alert = NSAlert(); alert.messageText = "文件未能保存"; alert.informativeText = error.localizedDescription
                    alert.beginSheetModal(for: self.window)
                }
            }
        }
    }
}

let application = NSApplication.shared
let delegate = WordIsle()
application.setActivationPolicy(.regular)
application.delegate = delegate
application.run()
