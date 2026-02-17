package com.speaknode.client.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Hub
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.speaknode.client.api.models.*
import com.speaknode.client.ui.components.AnalysisCards
import com.speaknode.client.ui.components.TaskStatusBadge

/**
 * Meeting detail screen — shows full detail for a single meeting.
 *
 * Displayed when a meeting card is clicked or after analysis completes.
 * Shows: metadata, topics, decisions, tasks, people, utterances.
 */
@Composable
fun MeetingDetailScreen(
    meetingDetail: MeetingDetail?,
    analysisResult: AnalysisResult?,
    isLoading: Boolean,
    onBack: () -> Unit,
    onOpenGraph: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxSize().padding(24.dp)) {
        // Header with back button
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
            }
            Spacer(Modifier.width(8.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = meetingDetail?.title?.ifBlank { "Meeting Detail" } ?: "Meeting Detail",
                    style = MaterialTheme.typography.headlineLarge,
                )
                if (meetingDetail != null) {
                    Text(
                        text = buildString {
                            if (meetingDetail.date.isNotBlank()) append("📅 ${meetingDetail.date}")
                            if (meetingDetail.sourceFile.isNotBlank()) {
                                if (isNotBlank()) append("  ·  ")
                                append("🎵 ${meetingDetail.sourceFile}")
                            }
                        },
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
            Button(
                onClick = onOpenGraph,
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF60A5FA)),
            ) {
                Icon(Icons.Default.Hub, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Knowledge Graph")
            }
        }

        Spacer(Modifier.height(16.dp))

        if (isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(12.dp))
                    Text("미팅 정보를 불러오는 중...", color = Color(0xFF9CA3AF))
                }
            }
            return
        }

        // Main content - analysis cards + utterances
        val result = analysisResult ?: meetingDetail?.toAnalysisResult()
        if (result == null) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("미팅 데이터를 찾을 수 없습니다.", color = Color(0xFF9CA3AF))
            }
            return
        }

        Row(modifier = Modifier.fillMaxSize()) {
            // Left: Analysis cards
            Column(modifier = Modifier.weight(1f)) {
                Text("📊 분석 결과", fontWeight = FontWeight.Bold, fontSize = 16.sp, color = Color(0xFFE5E7EB))
                Spacer(Modifier.height(8.dp))
                AnalysisCards(
                    result = result,
                    modifier = Modifier.fillMaxSize(),
                )
            }

            Spacer(Modifier.width(16.dp))

            // Right: Utterances timeline
            if (meetingDetail?.utterances?.isNotEmpty() == true) {
                Column(modifier = Modifier.width(350.dp)) {
                    Text(
                        "💬 Utterances (${meetingDetail.utterances.size})",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = Color(0xFF06B6D4),
                    )
                    Spacer(Modifier.height(8.dp))
                    LazyColumn(
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        items(meetingDetail.utterances) { utterance ->
                            UtteranceCard(utterance)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun UtteranceCard(utterance: Utterance) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0x0AFFFFFF), RoundedCornerShape(4.dp))
            .padding(8.dp),
        verticalAlignment = Alignment.Top,
    ) {
        // Time stamp
        Text(
            text = formatTime(utterance.startTime),
            fontSize = 11.sp,
            color = Color(0xFF06B6D4),
            fontWeight = FontWeight.Medium,
            modifier = Modifier.width(48.dp),
        )
        Spacer(Modifier.width(8.dp))
        Text(
            text = utterance.text,
            fontSize = 12.sp,
            color = Color(0xFFD1D5DB),
            lineHeight = 18.sp,
        )
    }
}

private fun formatTime(seconds: Double): String {
    val mins = (seconds / 60).toInt()
    val secs = (seconds % 60).toInt()
    return "%02d:%02d".format(mins, secs)
}

/** Convert MeetingDetail to AnalysisResult for display in AnalysisCards. */
private fun MeetingDetail.toAnalysisResult(): AnalysisResult = AnalysisResult(
    topics = topics,
    decisions = decisions,
    tasks = tasks,
    people = people,
)
