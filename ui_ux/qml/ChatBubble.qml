import QtQuick 2.15

Item {
    id: root

    property string role: "user"      // "user" | "assistant" | "system"
    property string content: ""

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
            if (role === "user")      return "#4A90D9"
            if (role === "assistant") return "#3C3C3C"
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
            font.family: "Malgun Gothic"
            wrapMode: Text.WordWrap
        }
    }
}
