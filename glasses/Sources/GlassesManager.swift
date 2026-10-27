import SwiftUI
import CoreBluetooth
import MWDATCore
import MWDATCamera

/// Registration with Meta AI + the glasses camera ("Chinnu's eyes").
@MainActor
final class GlassesManager: ObservableObject {
    @Published var registration = "checking..."
    @Published var isRegistered = false
    @Published var eyesOn = false
    @Published var allowCamera = UserDefaults.standard.bool(forKey: "allowCamera") {   // camera only switched on briefly when a question needs it
        didSet {
            UserDefaults.standard.set(allowCamera, forKey: "allowCamera")
            if allowCamera { Task { await self.ensureCameraPermission() } }
        }
    }
    @Published var eyesStatus = "off"
    @Published var preview: UIImage?
    @Published var error = ""
    @Published var devicesInfo = "no glasses found yet"
    @Published var hasActiveDevice = false
    @Published var needsFirmwareUpdate = false
    @Published var needsGlassesAppUpdate = false
    @Published var needsSDKUpdate = false
    @Published var bluetooth = "checking"
    @Published var bluetoothDenied = false

    private var selector: AutoDeviceSelector?
    private var session: DeviceSession?
    private var stream: MWDATCamera.Stream?
    private let tokens = ListenerTokenBag()          // stream listeners
    private var deviceTokens: [any AnyListenerToken] = []
    private var devices: [Device] = []
    private var latestJPEG: Data?

    init() {
        let sel = AutoDeviceSelector(wearables: Wearables.shared)
        selector = sel
        Task {
            for await state in Wearables.shared.registrationStateStream() {
                self.isRegistered = (state == .registered)
                self.registration = "\(state)"
            }
        }
        Task {
            for await ids in Wearables.shared.devicesStream() {
                self.devices = ids.compactMap { Wearables.shared.deviceForIdentifier($0) }
                self.deviceTokens.removeAll()
                for d in self.devices {
                    self.deviceTokens.append(d.addLinkStateListener { [weak self] _ in Task { @MainActor in self?.refresh() } })
                    self.deviceTokens.append(d.addCompatibilityListener { [weak self] _ in Task { @MainActor in self?.refresh() } })
                    self.deviceTokens.append(d.addDeviceStateListener { [weak self] _ in Task { @MainActor in self?.refresh() } })
                }
                self.refresh()
            }
        }
        Task {
            for await id in sel.activeDeviceStream() {
                self.hasActiveDevice = (id != nil)
                self.refresh()
            }
        }
        Task {   // Bluetooth permission of THIS app (no prompt is triggered by reading it)
            while true {
                self.refreshBluetooth()
                try? await Task.sleep(for: .seconds(3))
            }
        }
    }

    private func refreshBluetooth() {
        switch CBManager.authorization {
        case .allowedAlways: bluetooth = "allowed"; bluetoothDenied = false
        case .denied: bluetooth = "DENIED – turn it on in iPhone Settings › Chinnu"; bluetoothDenied = true
        case .restricted: bluetooth = "restricted"; bluetoothDenied = true
        case .notDetermined: bluetooth = "not asked yet"; bluetoothDenied = false
        @unknown default: bluetooth = "unknown"; bluetoothDenied = false
        }
    }

    private func refresh() {
        needsFirmwareUpdate = devices.contains { $0.compatibility() == .deviceUpdateRequired }
        needsSDKUpdate = devices.contains { $0.compatibility() == .sdkUpdateRequired }
        if devices.isEmpty { devicesInfo = "no glasses found yet"; return }
        devicesInfo = devices.map { d in
            var parts = ["link: \(d.linkState)", "compat: \(d.compatibility().displayString)"]
            if let b = d.batteryLevel { parts.append("battery \(b)%") }
            if d.donState != .unknown { parts.append("\(d.donState)") }
            if d.hingeState != .unknown { parts.append("hinge \(d.hingeState)") }
            return "\(d.nameOrId()) · " + parts.joined(separator: " · ")
        }.joined(separator: "\n") + (hasActiveDevice ? "\n✅ ready for camera" : "\n⏳ waiting for glasses link…")
    }

    func openFirmwareUpdate() { Task { try? await Wearables.shared.openFirmwareUpdate() } }
    func openGlassesAppUpdate() { Task { try? await Wearables.shared.openDATGlassesAppUpdate() } }
    func openSettings() { if let u = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(u) } }

    func register() {
        Task {
            do { try await Wearables.shared.startRegistration() }
            catch { self.error = error.localizedDescription }
        }
    }
    func unregister() {
        Task {
            do { try await Wearables.shared.startUnregistration() }
            catch { self.error = error.localizedDescription }
        }
    }

    /// Latest camera frame as JPEG (nil when eyes are off).
    func snapshot() -> Data? { eyesOn ? latestJPEG : nil }

    /// Turn the camera on just long enough for one good frame, then off again,
    /// so the glasses microphone (same Bluetooth link) comes straight back.
    func captureOnce() async -> Data? {
        guard allowCamera else { return nil }
        latestJPEG = nil
        await startEyes()
        guard eyesOn else { stopEyes(); return nil }
        var waited = 0, got = 0
        var jpg: Data? = nil
        while waited < 40 {                       // up to ~8 s; skip the first frames (exposure settling)
            try? await Task.sleep(for: .milliseconds(200)); waited += 1
            if let j = latestJPEG { got += 1; jpg = j; if got >= 3 { break } }
        }
        let shot = preview
        stopEyes()
        preview = shot                             // keep the last photo visible
        eyesStatus = jpg == nil ? "no picture from glasses" : "photo taken \(Date().formatted(date: .omitted, time: .shortened))"
        return jpg
    }

    private func ensureCameraPermission() async {
        do {
            if try await Wearables.shared.checkPermissionStatus(.camera) != .granted {
                eyesStatus = "asking permission in Meta AI..."
                let ok = try await Wearables.shared.requestPermission(.camera) == .granted
                eyesStatus = ok ? "camera allowed" : "camera permission denied"
                if !ok { allowCamera = false }
            } else { eyesStatus = "camera allowed" }
        } catch { self.error = "\(error)" }
    }

    func setEyes(_ on: Bool) {
        if on { Task { await startEyes() } } else { stopEyes() }
    }

    private func startEyes() async {
        error = ""; needsGlassesAppUpdate = false
        do {
            if try await Wearables.shared.checkPermissionStatus(.camera) != .granted {
                eyesStatus = "asking permission in Meta AI..."
                guard try await Wearables.shared.requestPermission(.camera) == .granted else {
                    eyesStatus = "camera permission denied"; eyesOn = false; return
                }
            }
            // Wait (up to 20 s) for the SDK to have a connected + compatible pair of glasses.
            var waited = 0
            while !hasActiveDevice && waited < 40 {
                eyesStatus = "waiting for glasses link… (\(devices.first.map { "\($0.linkState)" } ?? "no glasses"))"
                try await Task.sleep(for: .milliseconds(500)); waited += 1
            }
            guard hasActiveDevice, let sel = selector else {
                eyesStatus = "glasses never became ready — see status above"; eyesOn = false; return
            }
            eyesStatus = "connecting..."
            let s = try Wearables.shared.createSession(deviceSelector: sel)
            session = s
            s.errorPublisher.listen { [weak self] err in
                Task { @MainActor in
                    self?.error = "session: \(err)"
                    if err == .datAppOnTheGlassesUpdateRequired { self?.needsGlassesAppUpdate = true }
                }
            }.store(in: tokens)
            do throws(DeviceSessionError) { try s.start() }
            catch .datAppOnTheGlassesUpdateRequired { needsGlassesAppUpdate = true; throw DeviceSessionError.datAppOnTheGlassesUpdateRequired }
            for await state in s.stateStream() {
                eyesStatus = "session \(state)"
                if state == .started { break }
                if state == .stopped { eyesStatus = "glasses not available"; eyesOn = false; return }
            }
            let config = StreamConfiguration(videoCodec: .raw, resolution: .low, frameRate: 7)
            guard let camera = try s.addCamera(config: config) else { eyesStatus = "camera unavailable"; eyesOn = false; return }
            let st = camera.stream
            stream = st
            st.statePublisher.listen { [weak self] state in
                Task { @MainActor in self?.eyesStatus = "\(state)" }
            }.store(in: tokens)
            st.errorPublisher.listen { [weak self] err in
                Task { @MainActor in self?.error = "stream: \(err)" }
            }.store(in: tokens)
            var n = 0
            st.videoFramePublisher.listen { [weak self] frame in
                n += 1
                guard n % 2 == 0, let img = frame.makeUIImage() else { return }   // ~3-4 fps is plenty
                let jpg = img.jpegData(compressionQuality: 0.6)
                Task { @MainActor in self?.preview = img; self?.latestJPEG = jpg }
            }.store(in: tokens)
            st.start()
            eyesOn = true
        } catch {
            self.error = "\(error)"; eyesStatus = "failed"; eyesOn = false
        }
    }

    private func stopEyes() {
        stream?.stop(); stream = nil
        tokens.clear()
        session?.stop(); session = nil
        latestJPEG = nil; preview = nil
        eyesOn = false; eyesStatus = "off"
    }
}
