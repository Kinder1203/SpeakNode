package com.speaknode.client.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.speaknode.client.viewmodel.ServerStatus

/**
 * 네비게이션 사이드바.
 *
 * - 서버 연결 상태 표시
 * - 채팅 목록 및 선택
 * - 새 채팅 생성
 * - 화면 전환 (Meetings / Agent)
 */
@Composable
fun Sidebar(
    serverStatus: ServerStatus,
    chatIds: List<String>,
    activeChatId: String,
    activeScreen: String,
    onSelectChat: (String) -> Unit,
    onCreateChat: (String) -> Unit,
    onDeleteChat: (String) -> Unit,
    onScreenChange: (String) -> Unit,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var newChatName by remember { mutableStateOf("") }

    Column(
        modifier = modifier
            .width(260.dp)
            .fillMaxHeight()
            .background(MaterialTheme.colorScheme.surface)
            .padding(12.dp),
    ) {
        // --- Header ---
        Text(
            text = "🧠 SpeakNode",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary,
        )
        Spacer(Modifier.height(4.dp))
        StatusIndicator(serverStatus)

        Spacer(Modifier.height(16.dp))
        HorizontalDivider(color = MaterialTheme.colorScheme.outline)
        Spacer(Modifier.height(12.dp))

        // --- Navigation ---
        Text("NAVIGATION", style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.height(4.dp))

        NavItem("Meetings", Icons.Default.Event, activeScreen == "meetings") {
            onScreenChange("meetings")
        }
        NavItem("Agent", Icons.Default.SmartToy, activeScreen == "agent") {
            onScreenChange("agent")
        }

        Spacer(Modifier.height(16.dp))
        HorizontalDivider(color = MaterialTheme.colorScheme.outline)
        Spacer(Modifier.height(12.dp))

        // --- Chat Sessions ---
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text("CHATS", style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
            IconButton(onClick = onRefresh, modifier = Modifier.size(24.dp)) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh", modifier = Modifier.size(16.dp))
            }
        }
        Spacer(Modifier.height(4.dp))

        // New chat
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            OutlinedTextField(
                value = newChatName,
                onValueChange = { newChatName = it },
                placeholder = { Text("New chat name", style = MaterialTheme.typography.bodyMedium) },
                singleLine = true,
                modifier = Modifier.weight(1f).height(48.dp),
                textStyle = MaterialTheme.typography.bodyMedium,
            )
            Spacer(Modifier.width(4.dp))
            IconButton(
                onClick = {
                    if (newChatName.isNotBlank()) {
                        onCreateChat(newChatName.trim())
                        newChatName = ""
                    }
                },
                modifier = Modifier.size(36.dp),
            ) {
                Icon(Icons.Default.Add, contentDescription = "Create chat")
            }
        }
        Spacer(Modifier.height(8.dp))

        // Chat list
        LazyColumn(modifier = Modifier.weight(1f)) {
            items(chatIds) { chatId ->
                ChatItem(
                    chatId = chatId,
                    isActive = chatId == activeChatId,
                    onSelect = { onSelectChat(chatId) },
                    onDelete = { onDeleteChat(chatId) },
                )
            }
        }
    }
}

@Composable
private fun StatusIndicator(status: ServerStatus) {
    val (color, label) = when (status) {
        is ServerStatus.Connected -> MaterialTheme.colorScheme.secondary to "Connected"
        is ServerStatus.Connecting -> MaterialTheme.colorScheme.primary to "Connecting..."
        is ServerStatus.Error -> MaterialTheme.colorScheme.error to "Disconnected"
        is ServerStatus.Unknown -> MaterialTheme.colorScheme.outline to "Unknown"
    }

    Row(verticalAlignment = Alignment.CenterVertically) {
        Surface(
            shape = MaterialTheme.shapes.small,
            color = color,
            modifier = Modifier.size(8.dp),
        ) {}
        Spacer(Modifier.width(6.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = color)
    }
}

@Composable
private fun NavItem(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    isActive: Boolean,
    onClick: () -> Unit,
) {
    val bg = if (isActive) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surface
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .background(bg, shape = MaterialTheme.shapes.small)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Icon(icon, contentDescription = label, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(8.dp))
        Text(label, style = MaterialTheme.typography.titleMedium)
    }
}

@Composable
private fun ChatItem(
    chatId: String,
    isActive: Boolean,
    onSelect: () -> Unit,
    onDelete: () -> Unit,
) {
    val bg = if (isActive) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surface
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .background(bg, shape = MaterialTheme.shapes.small)
            .clickable(onClick = onSelect)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Icon(Icons.Default.Chat, contentDescription = null, modifier = Modifier.size(16.dp))
        Spacer(Modifier.width(8.dp))
        Text(
            text = chatId,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = if (isActive) FontWeight.Bold else FontWeight.Normal,
            modifier = Modifier.weight(1f),
        )
        IconButton(
            onClick = onDelete,
            modifier = Modifier.size(20.dp),
        ) {
            Icon(
                Icons.Default.DeleteOutline,
                contentDescription = "Delete",
                modifier = Modifier.size(14.dp),
                tint = MaterialTheme.colorScheme.error,
            )
        }
    }
}
