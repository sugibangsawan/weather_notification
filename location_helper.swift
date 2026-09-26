import AppKit
import CoreLocation

final class AppDelegate: NSObject, NSApplicationDelegate, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var outputPath: String?
    private var finished = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        outputPath = CommandLine.arguments.dropFirst().first
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        DispatchQueue.main.asyncAfter(deadline: .now() + 25) { [weak self] in
            self?.fail(
                "GPS timed out. Enable Weather Notification in System Settings > Privacy & Security > Location Services."
            )
        }
        startIfAllowed()
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        startIfAllowed()
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        let coordinate = location.coordinate
        write("\(coordinate.latitude),\(coordinate.longitude),\(location.horizontalAccuracy)\n")
        finish(code: 0)
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        fail(error.localizedDescription)
    }

    private func startIfAllowed() {
        switch manager.authorizationStatus {
        case .authorizedAlways, .authorizedWhenInUse:
            manager.startUpdatingLocation()
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .denied, .restricted:
            fail("Location permission denied. Enable Weather Notification in System Settings > Privacy & Security > Location Services.")
        @unknown default:
            fail("Location permission is unavailable.")
        }
    }

    private func write(_ line: String) {
        FileHandle.standardOutput.write(Data(line.utf8))
        if let outputPath {
            try? line.write(toFile: outputPath, atomically: true, encoding: .utf8)
        }
    }

    private func fail(_ message: String) {
        FileHandle.standardError.write(Data("\(message)\n".utf8))
        if let outputPath {
            try? "ERROR:\(message)\n".write(toFile: outputPath, atomically: true, encoding: .utf8)
        }
        finish(code: 1)
    }

    private func finish(code: Int32) {
        guard !finished else { return }
        finished = true
        manager.stopUpdatingLocation()
        NSApp.terminate(nil)
        exit(code)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.activate(ignoringOtherApps: true)
app.run()
