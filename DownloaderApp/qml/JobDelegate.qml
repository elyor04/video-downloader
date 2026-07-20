import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

Frame {
    id: root
    width: ListView.view ? ListView.view.width : implicitWidth

    function statusLine() {
        switch (jobState) {
        case "fetching":
            return qsTr("Fetching info…")
        case "awaiting_playlist_confirm":
            return qsTr("Waiting for playlist confirmation…")
        case "awaiting_login":
            return qsTr("Waiting for sign-in…")
        case "awaiting_password":
            return qsTr("Waiting for video password…")
        case "queued":
            return qsTr("Queued")
        case "downloading":
            if (stage === "converting")
                return qsTr("Converting…")
            if (playlistIndex > 0 && playlistCount > 0)
                return qsTr("Downloading (%1 of %2) — %3 of %4 (%5, ETA %6)")
                    .arg(playlistIndex).arg(playlistCount)
                    .arg(downloadedText).arg(totalText).arg(speedText).arg(etaText)
            return qsTr("%1 of %2 (%3, ETA %4)")
                .arg(downloadedText).arg(totalText).arg(speedText).arg(etaText)
        case "success":
            return qsTr("Done")
        case "error":
            return qsTr("Error: %1").arg(errorMessage)
        case "cancelled":
            return qsTr("Cancelled")
        default:
            return ""
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 12

        Rectangle {
            Layout.preferredWidth: 64
            Layout.preferredHeight: 64
            color: Material.color(Material.Grey, Material.Shade800)
            radius: 4
            clip: true

            Image {
                anchors.fill: parent
                source: thumbnail || ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: thumbnail.length > 0
            }

            Label {
                anchors.centerIn: parent
                visible: thumbnail.length === 0
                text: mode === "audio" ? "♪" : "▶"
                font.pixelSize: 24
                opacity: 0.6
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Label {
                Layout.fillWidth: true
                text: title
                elide: Text.ElideRight
                font.bold: true
            }

            ProgressBar {
                Layout.fillWidth: true
                indeterminate: progress < 0 && jobState !== "error" && jobState !== "cancelled"
                value: progress < 0 ? 0 : progress
            }

            Label {
                Layout.fillWidth: true
                text: root.statusLine()
                elide: Text.ElideRight
                opacity: 0.75
                font.pixelSize: 12
            }
        }

        RowLayout {
            spacing: 4

            ToolButton {
                text: qsTr("Open Folder")
                visible: canOpenFolder
                onClicked: backend.openOutputFolder(jobId)
            }
            ToolButton {
                text: qsTr("Cancel")
                visible: canCancel
                onClicked: backend.cancelJob(jobId)
            }
            ToolButton {
                text: qsTr("Remove")
                visible: canRemove
                onClicked: backend.removeJob(jobId)
            }
        }
    }
}
