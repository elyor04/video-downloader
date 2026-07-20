import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: root
    title: qsTr("Password required")
    modal: true
    standardButtons: Dialog.NoButton

    parent: Overlay.overlay
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)

    property string jobId: ""
    property string targetUrl: ""

    function openFor(id, forUrl) {
        jobId = id
        targetUrl = forUrl
        passwordField.text = ""
        open()
        passwordField.forceActiveFocus()
    }

    ColumnLayout {
        width: 320
        spacing: 8

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("This video requires a password:\n%1").arg(root.targetUrl)
            opacity: 0.8
            font.pixelSize: 12
        }
        TextField {
            id: passwordField
            Layout.fillWidth: true
            placeholderText: qsTr("Password")
            echoMode: TextInput.Password
        }
        RowLayout {
            Layout.fillWidth: true
            Button {
                text: qsTr("Skip")
                onClicked: {
                    backend.skipAuthentication(root.jobId)
                    root.close()
                }
            }
            Item { Layout.fillWidth: true }
            Button {
                text: qsTr("Submit")
                highlighted: true
                enabled: passwordField.text.length > 0
                onClicked: {
                    backend.submitPassword(root.jobId, passwordField.text)
                    root.close()
                }
            }
        }
    }

    Connections {
        target: backend
        function onPromptCancelled(id) {
            if (id === root.jobId)
                root.close()
        }
    }
}
