import QtQuick 2.15

Item {
    id: root

    property string role: "user"      // "user" | "assistant" | "system"
    property string content: ""
    property string fontFamily: ""
    property color  userBubbleColor:   "#4A90D9"
    property color  assistBubbleColor: "#3C3C3C"

    // 말풍선 너비: 부모의 75% 이하
    width: parent.width
    height: bubble.height + 8

    Rectangle {
        id: bubble

        width:  Math.min(bubbleText.implicitWidth + 24, parent.width * 0.75)
        height: bubbleText.implicitHeight + 16
        radius: 12

        // user: 오른쪽 정렬, assistant: 왼쪽 정렬
        anchors.right: role === "user"      ? parent.right : undefined
        anchors.left:  role !== "user"      ? parent.left  : undefined
        anchors.rightMargin: 4
        anchors.leftMargin:  4
        anchors.verticalCenter: parent.verticalCenter

        color: {
            if (role === "user")      return root.userBubbleColor
            if (role === "assistant") return root.assistBubbleColor
            return "#5A3A3A"  // system / error
        }

        Text {
            id: bubbleText
            anchors {
                left:   parent.left;  leftMargin:  12
                right:  parent.right; rightMargin: 12
                verticalCenter: parent.verticalCenter
            }
            text: root.content
            color: "#E0E0E0"
            font.pixelSize: 13
            font.family: root.fontFamily
            wrapMode: Text.WordWrap
            // HTML 링크(<a href>)가 포함된 메시지를 클릭 가능하게 렌더링한다.
            // AutoText: HTML 태그가 있으면 RichText로, 없으면 PlainText로 자동 전환.
            textFormat: Text.AutoText
            onLinkActivated: function(link) {
                // Qt.openUrlExternally는 WSL2에서 브라우저 감지 실패.
                // bridge.openUrl이 플랫폼별 올바른 방식으로 처리한다.
                bridge.openUrl(link)
            }
        }
    }
}
