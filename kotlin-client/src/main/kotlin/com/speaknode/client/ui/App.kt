package com.speaknode.client.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.speaknode.client.api.SpeakNodeApi
import com.speaknode.client.ui.components.Sidebar
import com.speaknode.client.ui.screens.AgentScreen
import com.speaknode.client.ui.screens.MeetingScreen
import com.speaknode.client.ui.theme.SpeakNodeTheme
import com.speaknode.client.viewmodel.AgentViewModel
import com.speaknode.client.viewmodel.AppViewModel

/**
 * 루트 Composable.
 *
 * Sidebar(네비게이션) + Content(화면) 2-pane 레이아웃.
 */
@Composable
fun App() {
    val api = remember { SpeakNodeApi() }
    val appVm = remember { AppViewModel(api) }
    val agentVm = remember { AgentViewModel(api) }

    // ViewModel → Compose State
    val serverStatus by appVm.serverStatus.collectAsState()
    val chatIds by appVm.chatIds.collectAsState()
    val activeChatId by appVm.activeChatId.collectAsState()
    val meetings by appVm.meetings.collectAsState()
    val analysisState by appVm.analysisState.collectAsState()
    val error by appVm.error.collectAsState()
    val agentMessages by agentVm.messages.collectAsState()
    val agentLoading by agentVm.isLoading.collectAsState()

    var activeScreen by remember { mutableStateOf("meetings") }

    DisposableEffect(Unit) {
        onDispose {
            appVm.dispose()
            agentVm.dispose()
        }
    }

    SpeakNodeTheme {
        // Error snackbar
        val snackbarHostState = remember { SnackbarHostState() }
        LaunchedEffect(error) {
            error?.let {
                snackbarHostState.showSnackbar(it, duration = SnackbarDuration.Short)
                appVm.clearError()
            }
        }

        Scaffold(
            snackbarHost = { SnackbarHost(snackbarHostState) },
        ) {
            Row(modifier = Modifier.fillMaxSize()) {
                // --- Sidebar ---
                Sidebar(
                    serverStatus = serverStatus,
                    chatIds = chatIds,
                    activeChatId = activeChatId,
                    activeScreen = activeScreen,
                    onSelectChat = { chatId ->
                        appVm.selectChat(chatId)
                        agentVm.clearHistory()
                    },
                    onCreateChat = { appVm.createChat(it) },
                    onDeleteChat = { appVm.deleteChat(it) },
                    onScreenChange = { activeScreen = it },
                    onRefresh = {
                        appVm.checkServerHealth()
                        appVm.loadChats()
                        appVm.loadMeetings()
                    },
                )

                VerticalDivider()

                // --- Content ---
                when (activeScreen) {
                    "meetings" -> MeetingScreen(
                        meetings = meetings,
                        analysisState = analysisState,
                        activeChatId = activeChatId,
                        onAnalyze = { path, title ->
                            appVm.analyzeAudio(path, title)
                        },
                    )
                    "agent" -> AgentScreen(
                        messages = agentMessages,
                        isLoading = agentLoading,
                        activeChatId = activeChatId,
                        onSendQuery = { question ->
                            agentVm.sendQuery(question, activeChatId)
                        },
                        onClearHistory = { agentVm.clearHistory() },
                    )
                }
            }
        }
    }
}
