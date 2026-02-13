package com.speaknode.client.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AudioFile
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.speaknode.client.api.models.MeetingSummary
import com.speaknode.client.viewmodel.AnalysisState

/**
 * 회의 목록 화면.
 *
 * - 파일 업로드 (오디오 분석 트리거)
 * - 분석 상태 표시
 * - 현재 채팅의 회의 목록 표시
 */
@Composable
fun MeetingScreen(
    meetings: List<MeetingSummary>,
    analysisState: AnalysisState,
    activeChatId: String,
    onAnalyze: (filePath: String, title: String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var filePath by remember { mutableStateOf("") }
    var meetingTitle by remember { mutableStateOf("") }

    Column(
        modifier = modifier.fillMaxSize().padding(24.dp),
    ) {
        // --- Header ---
        Text(
            text = "Meetings",
            style = MaterialTheme.typography.headlineLarge,
        )
        Text(
            text = "Chat: $activeChatId",
            style = MaterialTheme.typography.labelMedium,
        )

        Spacer(Modifier.height(20.dp))

        // --- Upload Section ---
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("오디오 분석", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(12.dp))

                OutlinedTextField(
                    value = filePath,
                    onValueChange = { filePath = it },
                    label = { Text("오디오 파일 경로") },
                    placeholder = { Text("/path/to/meeting.mp3") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))

                OutlinedTextField(
                    value = meetingTitle,
                    onValueChange = { meetingTitle = it },
                    label = { Text("회의 제목 (선택)") },
                    placeholder = { Text("2026-02-13 주간회의") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Button(
                        onClick = { onAnalyze(filePath.trim(), meetingTitle.trim()) },
                        enabled = filePath.isNotBlank() && analysisState !is AnalysisState.Analyzing,
                    ) {
                        Text("🚀 분석 시작")
                    }
                    Spacer(Modifier.width(12.dp))

                    when (analysisState) {
                        is AnalysisState.Analyzing -> {
                            CircularProgressIndicator(modifier = Modifier.size(24.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("분석 중...", style = MaterialTheme.typography.bodyMedium)
                        }
                        is AnalysisState.Complete -> {
                            Text(
                                "✅ 분석 완료 (Meeting: ${analysisState.response.meetingId})",
                                color = MaterialTheme.colorScheme.secondary,
                            )
                        }
                        is AnalysisState.Error -> {
                            Text(
                                "❌ ${analysisState.message}",
                                color = MaterialTheme.colorScheme.error,
                            )
                        }
                        else -> {}
                    }
                }
            }
        }

        Spacer(Modifier.height(24.dp))
        HorizontalDivider()
        Spacer(Modifier.height(16.dp))

        // --- Meeting List ---
        Text(
            text = "회의 목록 (${meetings.size}건)",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.height(8.dp))

        if (meetings.isEmpty()) {
            Text(
                "이 채팅에는 아직 분석된 회의가 없습니다.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.outline,
            )
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(meetings) { meeting ->
                    MeetingCard(meeting)
                }
            }
        }
    }
}

@Composable
private fun MeetingCard(meeting: MeetingSummary) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = meeting.title.ifBlank { meeting.id },
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(4.dp))
            Row {
                if (meeting.date.isNotBlank()) {
                    Icon(Icons.Default.CalendarToday, contentDescription = null, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(4.dp))
                    Text(meeting.date, style = MaterialTheme.typography.labelMedium)
                    Spacer(Modifier.width(16.dp))
                }
                if (meeting.sourceFile.isNotBlank()) {
                    Icon(Icons.Default.AudioFile, contentDescription = null, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(4.dp))
                    Text(meeting.sourceFile, style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}
