package com.speaknode.client.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.speaknode.client.api.models.*
import com.speaknode.client.ui.graph.TASK_STATUS_COLORS

// ── Colors matching index.html ──
private val TopicColor = Color(0xFF22C55E)
private val DecisionColor = Color(0xFFF472B6)
private val TaskColor = Color(0xFFF59E0B)
private val PersonColor = Color(0xFFA855F7)
private val EntityColor = Color(0xFFEC4899)
private val RelationColor = Color(0xFFEC4899)
private val LabelColor = Color(0xFF9CA3AF)
private val CardBg = Color(0x0AFFFFFF)
private val CardBorder = Color(0x14FFFFFF)

/**
 * Full analysis result cards panel.
 * Shows Topics, Decisions, Tasks, People, Entities, Relations.
 * Styled after index.html's right-side summary panel.
 */
@Composable
fun AnalysisCards(
    result: AnalysisResult,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(16.dp),
        contentPadding = PaddingValues(bottom = 16.dp),
    ) {
        // Statistics row
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                StatBadge("💡 ${result.topics.size}", TopicColor, Modifier.weight(1f))
                StatBadge("⚖️ ${result.decisions.size}", DecisionColor, Modifier.weight(1f))
                StatBadge("✅ ${result.tasks.size}", TaskColor, Modifier.weight(1f))
                StatBadge("👤 ${result.people.size}", PersonColor, Modifier.weight(1f))
                StatBadge("🔗 ${result.entities.size}", EntityColor, Modifier.weight(1f))
            }
        }

        // Topics
        if (result.topics.isNotEmpty()) {
            item {
                SectionHeader("💡 Topics (${result.topics.size})", TopicColor)
            }
            items(result.topics) { topic ->
                SummaryCard(borderColor = TopicColor) {
                    Text(topic.title, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, color = Color(0xFFE5E7EB))
                    if (topic.summary.isNotBlank()) {
                        Spacer(Modifier.height(2.dp))
                        Text(topic.summary, fontSize = 12.sp, color = LabelColor, maxLines = 3, overflow = TextOverflow.Ellipsis)
                    }
                    if (topic.proposer != "Unknown" && topic.proposer.isNotBlank()) {
                        Spacer(Modifier.height(2.dp))
                        Text("제안: ${topic.proposer}", fontSize = 11.sp, color = LabelColor)
                    }
                }
            }
        }

        // Decisions
        if (result.decisions.isNotEmpty()) {
            item {
                SectionHeader("⚖️ Decisions (${result.decisions.size})", DecisionColor)
            }
            items(result.decisions) { decision ->
                SummaryCard(borderColor = DecisionColor) {
                    Text(decision.description, fontSize = 13.sp, color = Color(0xFFE5E7EB))
                    if (decision.relatedTopic.isNotBlank()) {
                        Spacer(Modifier.height(2.dp))
                        Text("관련 주제: ${decision.relatedTopic}", fontSize = 11.sp, color = LabelColor)
                    }
                }
            }
        }

        // Tasks
        if (result.tasks.isNotEmpty()) {
            item {
                SectionHeader("✅ Tasks (${result.tasks.size})", TaskColor)
            }
            items(result.tasks) { task ->
                SummaryCard(borderColor = TaskColor) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            task.description,
                            fontSize = 13.sp,
                            color = Color(0xFFE5E7EB),
                            modifier = Modifier.weight(1f),
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Spacer(Modifier.width(8.dp))
                        TaskStatusBadge(task.status)
                    }
                    Spacer(Modifier.height(2.dp))
                    Text(
                        "${task.assignee} · ${task.deadline}",
                        fontSize = 11.sp,
                        color = LabelColor,
                    )
                }
            }
        }

        // People
        if (result.people.isNotEmpty()) {
            item {
                SectionHeader("👤 People (${result.people.size})", PersonColor)
            }
            items(result.people) { person ->
                SummaryCard(borderColor = PersonColor) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(person.name, fontWeight = FontWeight.Medium, fontSize = 13.sp, color = Color(0xFFE5E7EB))
                        Spacer(Modifier.width(8.dp))
                        Text(person.role, fontSize = 12.sp, color = LabelColor)
                    }
                }
            }
        }

        // Entities (grouped by type)
        if (result.entities.isNotEmpty()) {
            item {
                SectionHeader("🔗 Entities (${result.entities.size})", EntityColor)
            }
            val groups = result.entities.groupBy { it.entityType }
            groups.forEach { (type, items) ->
                item {
                    Text(
                        type.uppercase(),
                        fontSize = 11.sp,
                        color = Color(0xFF6B7280),
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(start = 4.dp, top = 4.dp, bottom = 2.dp),
                    )
                }
                items(items) { entity ->
                    SummaryCard(borderColor = EntityColor) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(entity.name, fontWeight = FontWeight.Medium, fontSize = 13.sp, color = Color(0xFFE5E7EB))
                            if (entity.description.isNotBlank()) {
                                Spacer(Modifier.width(6.dp))
                                Text("— ${entity.description}", fontSize = 12.sp, color = LabelColor, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                        }
                    }
                }
            }
        }

        // Relations
        if (result.relations.isNotEmpty()) {
            item {
                SectionHeader("↔️ Relations (${result.relations.size})", RelationColor)
            }
            items(result.relations) { rel ->
                SummaryCard(borderColor = RelationColor) {
                    Text(
                        "${rel.source}  —[${rel.relationType}]→  ${rel.target}",
                        fontSize = 12.sp,
                        color = Color(0xFFD1D5DB),
                    )
                }
            }
        }
    }
}

// ── Reusable sub-components ──

@Composable
fun SectionHeader(text: String, color: Color) {
    Text(
        text = text,
        fontSize = 14.sp,
        fontWeight = FontWeight.SemiBold,
        color = color,
        modifier = Modifier.padding(top = 4.dp),
    )
}

@Composable
fun SummaryCard(
    borderColor: Color,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(4.dp))
            .background(CardBg)
            .border(width = 0.dp, color = Color.Transparent, shape = RoundedCornerShape(4.dp))
            .drawLeftBorder(borderColor)
            .padding(start = 12.dp, end = 10.dp, top = 6.dp, bottom = 6.dp),
        content = content,
    )
}

@Composable
fun TaskStatusBadge(status: String) {
    val color = TASK_STATUS_COLORS[status] ?: Color(0xFFF59E0B)
    Text(
        text = status,
        fontSize = 11.sp,
        fontWeight = FontWeight.SemiBold,
        color = color,
        modifier = Modifier
            .background(color.copy(alpha = 0.15f), RoundedCornerShape(3.dp))
            .padding(horizontal = 6.dp, vertical = 1.dp),
    )
}

@Composable
fun StatBadge(text: String, color: Color, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .background(CardBg)
            .border(1.dp, CardBorder, RoundedCornerShape(6.dp))
            .padding(vertical = 6.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, fontSize = 12.sp, fontWeight = FontWeight.Medium, color = color)
    }
}

// ── Left border drawing modifier ──

private fun Modifier.drawLeftBorder(color: Color): Modifier =
    this.drawWithContent {
        drawContent()
        drawRect(
            color = color,
            topLeft = androidx.compose.ui.geometry.Offset(0f, 0f),
            size = androidx.compose.ui.geometry.Size(2.dp.toPx(), size.height),
        )
    }
