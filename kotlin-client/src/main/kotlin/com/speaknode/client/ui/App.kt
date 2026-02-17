package com.speaknode.client.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.speaknode.client.api.SpeakNodeApi
import com.speaknode.client.ui.components.Sidebar
import com.speaknode.client.ui.screens.AgentScreen
import com.speaknode.client.ui.screens.GraphScreen
import com.speaknode.client.ui.screens.MeetingDetailScreen
import com.speaknode.client.ui.screens.MeetingScreen
import com.speaknode.client.ui.theme.SpeakNodeTheme
import com.speaknode.client.viewmodel.AgentViewModel
import com.speaknode.client.viewmodel.AnalysisState
import com.speaknode.client.viewmodel.AppViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import javax.swing.JFileChooser
import javax.swing.filechooser.FileNameExtensionFilter

/**
 * Root Composable.
 *
 * 2-pane layout: Sidebar (navigation) + Content (screen).
 * Screens: meetings, meeting_detail, graph, agent.
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

    // New states
    val meetingDetail by appVm.meetingDetail.collectAsState()
    val meetingDetailLoading by appVm.meetingDetailLoading.collectAsState()
    val graphData by appVm.graphData.collectAsState()
    val graphLoading by appVm.graphLoading.collectAsState()

    var activeScreen by remember { mutableStateOf("meetings") }
    var selectedMeetingId by remember { mutableStateOf<String?>(null) }

    val coroutineScope = rememberCoroutineScope()

    // Auto-navigate to meeting detail after analysis completes
    LaunchedEffect(analysisState) {
        if (analysisState is AnalysisState.Complete) {
            val meetingId = (analysisState as AnalysisState.Complete).response.meetingId
            if (meetingId.isNotBlank()) {
                selectedMeetingId = meetingId
                appVm.loadMeetingDetail(meetingId)
                activeScreen = "meeting_detail"
            }
        }
    }

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
                // Sidebar 
                Sidebar(
                    serverStatus = serverStatus,
                    chatIds = chatIds,
                    activeChatId = activeChatId,
                    activeScreen = activeScreen,
                    onSelectChat = { chatId ->
                        appVm.selectChat(chatId)
                        agentVm.switchChat(chatId)
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

                // Content 
                when (activeScreen) {
                    "meetings" -> MeetingScreen(
                        meetings = meetings,
                        analysisState = analysisState,
                        activeChatId = activeChatId,
                        onAnalyze = { path, title ->
                            appVm.analyzeAudio(path, title)
                        },
                        onMeetingClick = { meetingId ->
                            selectedMeetingId = meetingId
                            appVm.loadMeetingDetail(meetingId)
                            activeScreen = "meeting_detail"
                        },
                    )
                    "meeting_detail" -> MeetingDetailScreen(
                        meetingDetail = meetingDetail,
                        analysisResult = (analysisState as? AnalysisState.Complete)?.response?.data,
                        isLoading = meetingDetailLoading,
                        onBack = {
                            activeScreen = "meetings"
                            appVm.clearMeetingDetail()
                        },
                        onOpenGraph = { activeScreen = "graph" },
                    )
                    "graph" -> GraphScreen(
                        graphData = graphData,
                        isLoading = graphLoading,
                        activeChatId = activeChatId,
                        onLoadGraph = { appVm.loadGraphData() },
                        onExportJson = {
                            coroutineScope.launch {
                                val file = withContext(Dispatchers.IO) { chooseExportFile("json") }
                                if (file != null) appVm.exportGraphJson(file)
                            }
                        },
                        onExportPng = {
                            coroutineScope.launch {
                                val file = withContext(Dispatchers.IO) { chooseExportFile("png") }
                                if (file != null) appVm.exportGraphPng(file)
                            }
                        },
                        onImportFile = {
                            coroutineScope.launch {
                                val file = withContext(Dispatchers.IO) { chooseImportFile() }
                                if (file != null) appVm.importGraphFile(file)
                            }
                        },
                        onUpdateNode = { nodeType, nodeId, fields ->
                            appVm.updateNode(nodeType, nodeId, fields)
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

// ── File chooser helpers ──

private fun chooseExportFile(extension: String): File? {
    val desc = if (extension == "png") "PNG Image (*.png)" else "JSON File (*.json)"
    val chooser = JFileChooser().apply {
        dialogTitle = "그래프 내보내기"
        fileFilter = FileNameExtensionFilter(desc, extension)
        isAcceptAllFileFilterUsed = false
    }
    return if (chooser.showSaveDialog(null) == JFileChooser.APPROVE_OPTION) {
        var file = chooser.selectedFile
        if (!file.name.lowercase().endsWith(".$extension")) {
            file = File(file.parentFile, "${file.name}.$extension")
        }
        file
    } else null
}

private fun chooseImportFile(): File? {
    val chooser = JFileChooser().apply {
        dialogTitle = "그래프 가져오기"
        fileFilter = FileNameExtensionFilter("SpeakNode Files (*.png, *.json)", "png", "json")
        isAcceptAllFileFilterUsed = false
    }
    return if (chooser.showOpenDialog(null) == JFileChooser.APPROVE_OPTION) {
        chooser.selectedFile
    } else null
}
