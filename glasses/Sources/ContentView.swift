import SwiftUI

struct ContentView: View {
    @EnvironmentObject var glasses: GlassesManager
    @EnvironmentObject var talker: Talker
    @State private var holding = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Text("🐕 Chinnu Glasses").font(.largeTitle.bold())

                GroupBox("1 · Glasses") {
                    HStack {
                        Text(glasses.isRegistered ? "✅ Connected to Meta AI" : "Not connected (\(glasses.registration))")
                        Spacer()
                        if !glasses.isRegistered { Button("Connect") { glasses.register() }.buttonStyle(.borderedProminent) }
                    }
                    Text(glasses.devicesInfo).font(.caption).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                    HStack {
                        Text("Bluetooth: \(glasses.bluetooth)").font(.caption).foregroundStyle(glasses.bluetoothDenied ? .red : .secondary)
                        if glasses.bluetoothDenied { Button("Open Settings") { glasses.openSettings() }.font(.caption) }
                    }.frame(maxWidth: .infinity, alignment: .leading)
                    if glasses.needsFirmwareUpdate { Button("Update glasses firmware (Meta AI)") { glasses.openFirmwareUpdate() }.buttonStyle(.borderedProminent).tint(.orange) }
                    if glasses.needsGlassesAppUpdate { Button("Update Chinnu app on glasses (Meta AI)") { glasses.openGlassesAppUpdate() }.buttonStyle(.borderedProminent).tint(.orange) }
                    if glasses.needsSDKUpdate { Text("App needs a rebuild with a newer Meta SDK").font(.caption).foregroundStyle(.orange) }
                    if glasses.isRegistered { Button("Disconnect from Meta AI") { glasses.unregister() }.font(.caption2).foregroundStyle(.secondary) }
                }

                GroupBox("2 · Talk") {
                    VStack(alignment: .leading, spacing: 10) {
                        Toggle("Hands-free (say \"Chinnu …\")", isOn: Binding(get: { talker.handsFree }, set: { talker.setHandsFree($0) }))
                        Text(talker.status).font(.callout).foregroundStyle(.secondary)
                        ProgressView(value: Double(min(1, talker.level * 12))).tint(.cyan)
                        if !talker.route.isEmpty { Text("Mic: \(talker.route)").font(.caption).foregroundStyle(.secondary) }
                        Text(holding ? "Listening… release to send" : "Hold to talk")
                            .frame(maxWidth: .infinity).padding(.vertical, 22)
                            .background(holding ? Color.orange : Color.cyan).foregroundColor(.black)
                            .clipShape(RoundedRectangle(cornerRadius: 14)).font(.title3.bold())
                            .gesture(DragGesture(minimumDistance: 0)
                                .onChanged { _ in if !holding { holding = true; talker.pttDown() } }
                                .onEnded { _ in holding = false; talker.pttUp() })
                    }
                }

                GroupBox("3 · Chinnu's eyes (glasses camera)") {
                    VStack(alignment: .leading) {
                        Toggle("Chinnu can use the camera when asked", isOn: $glasses.allowCamera)
                        Text("Ask \"Chinnu, idi enti?\" — the camera turns on for a moment, takes a photo, and turns off so the mic keeps working.").font(.caption).foregroundStyle(.secondary)
                        Text(glasses.eyesStatus).font(.caption).foregroundStyle(.secondary)
                        if let img = glasses.preview {
                            Image(uiImage: img).resizable().scaledToFit().frame(maxHeight: 260).clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                    }
                }

                if !talker.you.isEmpty || !talker.reply.isEmpty {
                    GroupBox("Last") {
                        VStack(alignment: .leading, spacing: 6) {
                            if !talker.you.isEmpty { Text("You: \(talker.you)") }
                            if !talker.reply.isEmpty { Text("Chinnu: \(talker.reply)").foregroundStyle(.cyan) }
                        }.frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                if !glasses.error.isEmpty { Text(glasses.error).foregroundStyle(.red).font(.caption) }
            }.padding()
        }
        .onAppear { talker.ensureEngine() }
    }
}
