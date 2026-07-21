import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs

Frame {
    id: root

    function looksLikeUrl(text) {
        return /^https?:\/\/\S+/i.test(text)
    }

    Timer {
        id: previewDebounce
        interval: 600
        onTriggered: {
            var text = urlField.text.trim()
            backend.requestPreview(root.looksLikeUrl(text) ? text : "")
        }
    }

    Connections {
        target: backend
        function onJobAdded() {
            urlField.clear()
            urlField.forceActiveFocus()
        }
        function onModeChanged() {
            convertCombo.currentIndex = 0
            backend.resetConvertToOriginal()
        }
        function onResolutionOptionsChanged() {
            resolutionCombo.currentIndex = 0
            backend.resetResolutionToBest()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            TextField {
                id: urlField
                Layout.fillWidth: true
                placeholderText: qsTr("Paste a video or playlist URL…")
                selectByMouse: true
                onAccepted: {
                    if (addButton.enabled)
                        backend.addJob(urlField.text)
                }
                onTextChanged: previewDebounce.restart()
            }

            ButtonGroup { id: modeGroup }

            RadioButton {
                text: qsTr("Video")
                checked: backend.mode === "video"
                ButtonGroup.group: modeGroup
                onClicked: backend.setMode("video")
            }
            RadioButton {
                text: qsTr("Audio")
                checked: backend.mode === "audio"
                ButtonGroup.group: modeGroup
                onClicked: backend.setMode("audio")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: backend.previewState !== "idle"
            spacing: 8

            BusyIndicator {
                visible: backend.previewState === "fetching"
                implicitWidth: 18
                implicitHeight: 18
                running: visible
            }

            Image {
                visible: backend.previewState === "ready" && backend.previewThumbnail.length > 0
                source: visible ? backend.previewThumbnail : ""
                Layout.preferredWidth: 36
                Layout.preferredHeight: 36
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
            }

            Label {
                Layout.fillWidth: true
                elide: Text.ElideRight
                font.pixelSize: 12
                opacity: 0.85
                color: backend.previewState === "error" ? Material.color(Material.Red) : Material.foreground
                text: {
                    switch (backend.previewState) {
                    case "fetching":
                        return qsTr("Looking up video info…")
                    case "ready":
                        return backend.previewIsPlaylist
                            ? qsTr("Playlist: %1 (%2 items)").arg(backend.previewTitle).arg(backend.previewPlaylistCount)
                            : backend.previewTitle
                    case "error":
                        return qsTr("Couldn't load info: %1").arg(backend.previewError)
                    default:
                        return ""
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ComboBox {
                id: resolutionCombo
                visible: backend.mode === "video"
                Layout.preferredWidth: 160
                model: backend.resolutionModel
                textRole: "text"
                valueRole: "value"
                onActivated: backend.setResolution(currentValue)
            }

            ComboBox {
                id: convertCombo
                Layout.preferredWidth: 140
                model: backend.convertModel
                textRole: "text"
                valueRole: "value"
                onActivated: backend.setConvertTo(currentValue)
            }

            TextField {
                Layout.fillWidth: true
                placeholderText: qsTr("File name (optional)")
                onTextChanged: backend.setFileName(text)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            TextField {
                Layout.fillWidth: true
                readOnly: true
                text: backend.outputDir
            }

            Button {
                text: qsTr("Browse…")
                onClicked: folderDialog.open()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Button {
                id: addButton
                text: qsTr("Download")
                highlighted: true
                enabled: urlField.text.trim().length > 0
                    && backend.previewState === "ready"
                    && backend.previewUrl === urlField.text.trim()
                onClicked: backend.addJob(urlField.text)
            }
        }
    }

    FolderDialog {
        id: folderDialog
        title: qsTr("Select Output Directory")
        onAccepted: backend.setOutputDirFromUrl(selectedFolder)
    }
}
