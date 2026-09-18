import QtQuick
import QtQuick.VirtualKeyboard
import QtQuick.VirtualKeyboard.Settings

// 根就是 InputPanel；高度跟键盘内容（含候选栏），不要被 QQuickWidget 压扁。
InputPanel {
    id: inputPanel
    Component.onCompleted: {
        VirtualKeyboardSettings.activeLocales = ["zh_CN", "zh_TW", "en_US"]
        VirtualKeyboardSettings.locale = "zh_CN"
    }
}
