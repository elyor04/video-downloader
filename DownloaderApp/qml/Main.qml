import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import Qt.labs.platform as Labs

ApplicationWindow {
    id: window
    width: 680
    height: 760
    minimumWidth: 520
    minimumHeight: 480
    visible: true
    title: qsTr("Video Downloader")

    Material.theme: Material.Dark
    Material.accent: "#2196F3"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        RowLayout {
            Layout.fillWidth: true

            Label {
                text: qsTr("Video Downloader")
                font.pixelSize: 20
                font.bold: true
                Layout.fillWidth: true
            }

            ComboBox {
                id: languageCombo
                readonly property var codes: ["en", "ru", "uz"]
                Layout.preferredWidth: 140
                model: ["English", "Русский", "Oʻzbekcha"]
                currentIndex: codes.indexOf(backend.language)
                onActivated: backend.setLanguage(codes[currentIndex])
            }
        }

        AddJobSection {
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: qsTr("Downloads")
                font.bold: true
                Layout.fillWidth: true
            }
            ToolButton {
                text: qsTr("Clear Completed")
                onClicked: backend.clearCompleted()
            }
        }

        QueueListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }

    Dialog {
        id: errorDialog
        title: qsTr("Error")
        modal: true
        standardButtons: Dialog.Ok

        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)

        property string message: ""

        Label {
            width: 320
            wrapMode: Text.WordWrap
            text: errorDialog.message
        }
    }

    PlaylistConfirmDialog { id: playlistDialog }
    LoginDialog { id: loginDialog }
    PasswordDialog { id: passwordDialog }

    Labs.SystemTrayIcon {
        id: trayIcon
        visible: true
        icon.source: "../resources/icon.png"
        onMessageClicked: {
            window.show()
            window.raise()
            window.requestActivate()
        }
    }

    Connections {
        target: backend
        function onErrorOccurred(message) {
            errorDialog.message = message
            errorDialog.open()
        }
        function onPlaylistDetected(jobId, count) {
            playlistDialog.openFor(jobId, count)
        }
        function onLoginRequested(jobId, url) {
            loginDialog.openFor(jobId, url)
        }
        function onPasswordRequested(jobId, url) {
            passwordDialog.openFor(jobId, url)
        }
        function onNotifyRequested(title, message) {
            if (trayIcon.supportsMessages)
                trayIcon.showMessage(title, message)
        }
    }
}
