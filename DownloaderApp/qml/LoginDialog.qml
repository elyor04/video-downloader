import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: root
    title: qsTr("Sign in required")
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
        usernameField.text = ""
        passwordField.text = ""
        open()
        usernameField.forceActiveFocus()
    }

    ColumnLayout {
        width: 320
        spacing: 8

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("This site requires an account to continue:\n%1").arg(root.targetUrl)
            opacity: 0.8
            font.pixelSize: 12
        }
        TextField {
            id: usernameField
            Layout.fillWidth: true
            placeholderText: qsTr("Username or email")
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
                text: qsTr("Sign In")
                highlighted: true
                enabled: usernameField.text.length > 0 || passwordField.text.length > 0
                onClicked: {
                    backend.submitLogin(root.jobId, usernameField.text, passwordField.text)
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
