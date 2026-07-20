import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root

    ListView {
        id: listView
        anchors.fill: parent
        spacing: 8
        clip: true
        model: backend.queueModel
        delegate: JobDelegate {
            width: listView.width
        }

        ScrollBar.vertical: ScrollBar {}
    }

    Label {
        anchors.centerIn: parent
        visible: listView.count === 0
        text: qsTr("No downloads yet. Paste a URL above to get started.")
        opacity: 0.6
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        width: parent.width * 0.6
    }
}
