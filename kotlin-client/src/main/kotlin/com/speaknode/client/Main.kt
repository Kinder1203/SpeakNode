package com.speaknode.client

import androidx.compose.ui.unit.DpSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.WindowState
import androidx.compose.ui.window.application
import com.speaknode.client.ui.App

fun main() = application {
    Window(
        onCloseRequest = ::exitApplication,
        title = "SpeakNode — Intelligent Meeting Analyst",
        state = WindowState(size = DpSize(1200.dp, 800.dp)),
    ) {
        App()
    }
}
