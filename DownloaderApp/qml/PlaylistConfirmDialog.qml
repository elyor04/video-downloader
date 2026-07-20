import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: root
    title: qsTr("Playlist detected")
    modal: true
    standardButtons: Dialog.Yes | Dialog.No

    parent: Overlay.overlay
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)

    property string jobId: ""
    property int count: 0

    function openFor(id, itemCount) {
        jobId = id
        count = itemCount
        open()
    }

    ColumnLayout {
        width: 320

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: root.count > 0
                ? qsTr("This URL is a playlist with %1 items. Download all of them?").arg(root.count)
                : qsTr("This URL is a playlist. Download all items?")
        }
    }

    onAccepted: backend.confirmPlaylist(jobId, true)
    onRejected: backend.confirmPlaylist(jobId, false)

    Connections {
        target: backend
        function onPromptCancelled(id) {
            if (id === root.jobId)
                root.close()
        }
    }
}
