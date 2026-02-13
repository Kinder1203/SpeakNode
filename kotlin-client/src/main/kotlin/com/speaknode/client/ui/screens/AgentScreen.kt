package com.speaknode.client.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.*
import androidx.compose.ui.unit.dp
import com.speaknode.client.viewmodel.ChatMessage

/**
 * AI Agent 대화 화면.
 *
 * - 채팅 형태의 대화 UI
 * - 질문 입력 및 전송
 * - 실시간 로딩 표시
 */
@Composable
fun AgentScreen(
    messages: List<ChatMessage>,
    isLoading: Boolean,
    activeChatId: String,
    onSendQuery: (String) -> Unit,
    onClearHistory: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var inputText by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    // 새 메시지가 추가되면 자동 스크롤
    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.lastIndex)
        }
    }

    Column(modifier = modifier.fillMaxSize().padding(24.dp)) {
        // --- Header ---
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "🤖 AI Agent",
                    style = MaterialTheme.typography.headlineLarge,
                )
                Text(
                    text = "Chat: $activeChatId — 회의 데이터에 대해 자유롭게 질문하세요",
                    style = MaterialTheme.typography.labelMedium,
                )
            }

            if (messages.isNotEmpty()) {
                IconButton(onClick = onClearHistory) {
                    Icon(Icons.Default.DeleteOutline, contentDescription = "Clear history")
                }
            }
        }

        Spacer(Modifier.height(16.dp))

        // --- Messages ---
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (messages.isEmpty()) {
                item {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 40.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(
                            "💡 예시 질문",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Spacer(Modifier.height(12.dp))

                        val examples = listOf(
                            "이번 회의에서 결정된 사항을 알려줘",
                            "누가 어떤 할 일을 맡았어?",
                            "회의 결과를 팀원에게 이메일로 보내줘",
                        )
                        examples.forEach { example ->
                            OutlinedButton(
                                onClick = { onSendQuery(example) },
                                modifier = Modifier.padding(vertical = 2.dp),
                            ) {
                                Text(example)
                            }
                        }
                    }
                }
            }

            items(messages) { msg ->
                MessageBubble(msg)
            }

            if (isLoading) {
                item {
                    Row(
                        modifier = Modifier.padding(start = 12.dp, top = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("분석 중...", style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        }

        Spacer(Modifier.height(12.dp))

        // --- Input ---
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            OutlinedTextField(
                value = inputText,
                onValueChange = { inputText = it },
                placeholder = { Text("회의 데이터에 대해 질문하세요...") },
                singleLine = true,
                enabled = !isLoading,
                modifier = Modifier
                    .weight(1f)
                    .onKeyEvent { event ->
                        if (event.key == Key.Enter && event.type == KeyEventType.KeyDown && !event.isShiftPressed) {
                            if (inputText.isNotBlank() && !isLoading) {
                                onSendQuery(inputText.trim())
                                inputText = ""
                            }
                            true
                        } else false
                    },
            )
            Spacer(Modifier.width(8.dp))
            IconButton(
                onClick = {
                    if (inputText.isNotBlank() && !isLoading) {
                        onSendQuery(inputText.trim())
                        inputText = ""
                    }
                },
                enabled = inputText.isNotBlank() && !isLoading,
            ) {
                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
            }
        }
    }
}

@Composable
private fun MessageBubble(message: ChatMessage) {
    val isUser = message.role == "user"
    val isError = message.role == "error"

    val bgColor = when {
        isUser -> MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
        isError -> MaterialTheme.colorScheme.error.copy(alpha = 0.15f)
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    val textColor = when {
        isError -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.onSurface
    }
    val alignment = if (isUser) Alignment.End else Alignment.Start

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = alignment,
    ) {
        Text(
            text = if (isUser) "You" else if (isError) "Error" else "Agent",
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(start = 12.dp, bottom = 2.dp),
        )
        Surface(
            shape = RoundedCornerShape(12.dp),
            color = bgColor,
            modifier = Modifier.widthIn(max = 600.dp),
        ) {
            Text(
                text = message.content,
                color = textColor,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(12.dp),
            )
        }
    }
}
