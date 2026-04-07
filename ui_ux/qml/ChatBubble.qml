import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root

    property string role: "user"      // "user" | "assistant" | "system" | "narrator"
    property string content: ""
    property string fontFamily: ""
    property color  userBubbleColor:   "#4A90D9"
    property color  assistBubbleColor: "#3C3C3C"

    // 편집 기능 — assistant/narrator 버블에서만 활성화
    property int    modelIndex: -1
    property bool   editable:   false

    // 편집 완료 시 부모(main.qml delegate)로 전달
    signal editConfirmed(int idx, string oldText, string newText)

    property bool   _isEditing:  false
    property string _editBuffer: ""
    property string _oldBuffer:  ""

    // 말풍선 너비: 부모의 75% 이하 (narrator는 90% 가운데 정렬)
    width: parent.width
    height: bubble.height + 8

    Rectangle {
        id: bubble

        width: {
            if (root._isEditing)
                return parent.width * (role === "narrator" ? 0.9 : 0.78)
            if (role === "narrator")
                return Math.min(bubbleText.implicitWidth + 32, parent.width * 0.9)
            return Math.min(bubbleText.implicitWidth + 24, parent.width * 0.75)
        }
        height: {
            if (root._isEditing)
                return editArea.implicitHeight + editButtons.height + 28
            return bubbleText.implicitHeight + 16
        }
        radius: role === "narrator" ? 6 : 12

        // user: 오른쪽 정렬, narrator: 가운데, assistant: 왼쪽 정렬
        anchors.right:            role === "user"     ? parent.right     : undefined
        anchors.left:             role === "assistant" || role === "system" ? parent.left : undefined
        anchors.horizontalCenter: role === "narrator" ? parent.horizontalCenter : undefined
        anchors.rightMargin: 4
        anchors.leftMargin:  4
        anchors.verticalCenter: parent.verticalCenter

        color: {
            if (role === "user")      return root.userBubbleColor
            if (role === "assistant") return root.assistBubbleColor
            if (role === "narrator")  return "#1E2A30"   // 어두운 청회색 — 나레이션 배경
            return "#5A3A3A"  // system / error
        }
        border.color: {
            if (role === "narrator")  return root._isEditing ? "#6A9AAA" : "#4A6A7A"
            if (root._isEditing)      return "#6A8AAA"
            return "transparent"
        }
        border.width: role === "narrator" || root._isEditing ? 1 : 0

        Behavior on width  { NumberAnimation { duration: 80 } }
        Behavior on height { NumberAnimation { duration: 80 } }

        // ── 일반 표시 텍스트 ─────────────────────────────────────────────
        Text {
            id: bubbleText
            visible: !root._isEditing
            anchors {
                left:   parent.left;  leftMargin:  12
                right:  parent.right; rightMargin: 12
                verticalCenter: parent.verticalCenter
            }
            text: root.content
            color: role === "narrator" ? "#8AAABB" : "#E0E0E0"
            font.pixelSize: role === "narrator" ? 12 : 13
            font.family: root.fontFamily
            font.italic: role === "narrator"
            horizontalAlignment: role === "narrator" ? Text.AlignHCenter : Text.AlignLeft
            wrapMode: Text.WordWrap
            textFormat: Text.AutoText
            onLinkActivated: function(link) {
                bridge.openUrl(link)
            }
        }

        // ── 편집 중 TextEdit ─────────────────────────────────────────────
        TextEdit {
            id: editArea
            visible: root._isEditing
            anchors {
                top:   parent.top;   topMargin:  10
                left:  parent.left;  leftMargin: 12
                right: parent.right; rightMargin: 12
            }
            text: root._editBuffer
            color: "#E8E8E8"
            font.pixelSize: role === "narrator" ? 12 : 13
            font.family: root.fontFamily
            font.italic: role === "narrator"
            wrapMode: TextEdit.WordWrap
            selectionColor: "#4A7AB5"
            onTextChanged: root._editBuffer = text

            // 활성화 시 전체 선택
            onVisibleChanged: {
                if (visible) {
                    forceActiveFocus()
                    selectAll()
                }
            }

            // Ctrl+Enter 확인 / Escape 취소
            Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Return && (event.modifiers & Qt.ControlModifier)) {
                    _confirm()
                    event.accepted = true
                } else if (event.key === Qt.Key_Escape) {
                    _cancel()
                    event.accepted = true
                }
            }
        }

        // ── 확인 / 취소 버튼 ────────────────────────────────────────────
        Row {
            id: editButtons
            visible: root._isEditing
            anchors {
                bottom: parent.bottom; bottomMargin: 6
                right:  parent.right;  rightMargin:  10
            }
            spacing: 6

            // 취소
            Rectangle {
                width: 24; height: 20
                radius: 4
                color: cancelHover.containsMouse ? "#5A3A3A" : "#3A2A2A"
                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: "#CC8888"
                    font.pixelSize: 11
                }
                MouseArea {
                    id: cancelHover
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: _cancel()
                }
            }

            // 확인
            Rectangle {
                width: 24; height: 20
                radius: 4
                color: confirmHover.containsMouse ? "#2A4A3A" : "#1A3A2A"
                Text {
                    anchors.centerIn: parent
                    text: "✓"
                    color: "#88CC88"
                    font.pixelSize: 11
                }
                MouseArea {
                    id: confirmHover
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: _confirm()
                }
            }
        }

        // ── 더블클릭으로 편집 시작 ───────────────────────────────────────
        MouseArea {
            anchors.fill: parent
            visible: root.editable && !root._isEditing
            hoverEnabled: true
            cursorShape: root.editable ? Qt.IBeamCursor : Qt.ArrowCursor
            onDoubleClicked: {
                root._oldBuffer  = root.content
                root._editBuffer = root.content
                root._isEditing  = true
            }
        }
    }

    // ── 내부 함수 ────────────────────────────────────────────────────────
    function _confirm() {
        var newText = root._editBuffer.trim()
        if (newText.length === 0) {
            _cancel()
            return
        }
        root._isEditing = false
        if (newText !== root._oldBuffer)
            root.editConfirmed(root.modelIndex, root._oldBuffer, newText)
    }

    function _cancel() {
        root._editBuffer = root._oldBuffer
        root._isEditing  = false
    }
}
