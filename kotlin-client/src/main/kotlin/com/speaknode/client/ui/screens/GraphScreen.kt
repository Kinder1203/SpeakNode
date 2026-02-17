package com.speaknode.client.ui.screens

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.speaknode.client.api.models.*
import com.speaknode.client.ui.components.SectionHeader
import com.speaknode.client.ui.components.SummaryCard
import com.speaknode.client.ui.components.TaskStatusBadge
import com.speaknode.client.ui.graph.*

/**
 * Full Knowledge Graph screen for the current chat.
 *
 * Layout (matching index.html):
 * ┌─────────────────────────────────────┬──────────────┐
 * │ Toolbar (toggle, export, import)    │              │
 * ├─────────────────────────────────────┤  Right Panel │
 * │                                     │  - Summary   │
 * │         Graph Canvas                │  - Node Info │
 * │    (Force-Directed Visualization)   │  - Schema    │
 * │                                     │              │
 * └─────────────────────────────────────┴──────────────┘
 */
@Composable
fun GraphScreen(
    graphData: GraphDisplayData?,
    isLoading: Boolean,
    activeChatId: String,
    onLoadGraph: () -> Unit,
    onExportJson: () -> Unit,
    onExportPng: () -> Unit,
    onImportFile: () -> Unit,
    onUpdateNode: (nodeType: String, nodeId: String, fields: Map<String, String>) -> Unit,
    modifier: Modifier = Modifier,
) {
    // Auto-load graph on first display / chat change
    LaunchedEffect(activeChatId) {
        onLoadGraph()
    }

    var showUtterances by remember { mutableStateOf(false) }
    var selectedNodeId by remember { mutableStateOf<String?>(null) }
    var showEditor by remember { mutableStateOf(false) }

    Column(modifier = modifier.fillMaxSize()) {
        // Toolbar
        GraphToolbar(
            showUtterances = showUtterances,
            onToggleUtterances = { showUtterances = it },
            onExportJson = onExportJson,
            onExportPng = onExportPng,
            onImportFile = onImportFile,
            onRefresh = onLoadGraph,
            activeChatId = activeChatId,
        )

        if (isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(12.dp))
                    Text("그래프 데이터 로딩 중...", color = Color(0xFF9CA3AF))
                }
            }
            return
        }

        if (graphData == null || graphData.nodes.isEmpty()) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("🕸️", fontSize = 48.sp)
                    Spacer(Modifier.height(12.dp))
                    Text("이 채팅에는 아직 분석된 데이터가 없습니다", color = Color(0xFF4B5563))
                    Text("미팅 탭에서 오디오를 분석하거나 PNG를 가져오세요", fontSize = 12.sp, color = Color(0xFF4B5563))
                }
            }
            return
        }

        // Main content: Canvas + Right Panel
        Row(modifier = Modifier.fillMaxSize()) {
            // Center: Graph Canvas
            GraphCanvas(
                data = graphData,
                showUtterances = showUtterances,
                selectedNodeId = selectedNodeId,
                onNodeClick = { selectedNodeId = it },
                modifier = Modifier.weight(1f),
            )

            // Right Panel
            RightPanel(
                graphData = graphData,
                selectedNodeId = selectedNodeId,
                showEditor = showEditor,
                onEditClick = { showEditor = true },
                onDismissEditor = { showEditor = false },
                onUpdateNode = onUpdateNode,
                modifier = Modifier.width(320.dp),
            )
        }
    }

    // Node editor dialog
    if (showEditor && selectedNodeId != null) {
        val selectedNode = graphData?.nodes?.find { it.id == selectedNodeId }
        if (selectedNode != null) {
            NodeEditorDialog(
                node = selectedNode,
                onDismiss = { showEditor = false },
                onSave = { nodeType, nodeId, fields ->
                    onUpdateNode(nodeType, nodeId, fields)
                    showEditor = false
                },
            )
        }
    }
}

// ── Toolbar ──

@Composable
private fun GraphToolbar(
    showUtterances: Boolean,
    onToggleUtterances: (Boolean) -> Unit,
    onExportJson: () -> Unit,
    onExportPng: () -> Unit,
    onImportFile: () -> Unit,
    onRefresh: () -> Unit,
    activeChatId: String,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0xFF000000))
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "🕸️ Knowledge Graph",
            fontWeight = FontWeight.SemiBold,
            fontSize = 18.sp,
            color = Color(0xFF60A5FA),
        )
        Text(
            "  —  $activeChatId",
            fontSize = 12.sp,
            color = Color(0xFF9CA3AF),
        )

        Spacer(Modifier.weight(1f))

        // Utterance toggle
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(
                checked = showUtterances,
                onCheckedChange = onToggleUtterances,
                colors = CheckboxDefaults.colors(
                    checkedColor = Color(0xFF06B6D4),
                    uncheckedColor = Color(0xFF4B5563),
                ),
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(4.dp))
            Text("Utterances", fontSize = 12.sp, color = Color(0xFF9CA3AF))
        }

        Spacer(Modifier.width(16.dp))

        // Export/Import buttons
        IconButton(onClick = onExportPng, modifier = Modifier.size(32.dp)) {
            Icon(Icons.Default.Image, contentDescription = "Export PNG", tint = Color(0xFF60A5FA), modifier = Modifier.size(18.dp))
        }
        IconButton(onClick = onExportJson, modifier = Modifier.size(32.dp)) {
            Icon(Icons.Default.FileDownload, contentDescription = "Export JSON", tint = Color(0xFF22C55E), modifier = Modifier.size(18.dp))
        }
        IconButton(onClick = onImportFile, modifier = Modifier.size(32.dp)) {
            Icon(Icons.Default.FileUpload, contentDescription = "Import", tint = Color(0xFFF59E0B), modifier = Modifier.size(18.dp))
        }
        IconButton(onClick = onRefresh, modifier = Modifier.size(32.dp)) {
            Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = Color(0xFF9CA3AF), modifier = Modifier.size(18.dp))
        }
    }
}

// ── Right Panel ──

@Composable
private fun RightPanel(
    graphData: GraphDisplayData,
    selectedNodeId: String?,
    showEditor: Boolean,
    onEditClick: () -> Unit,
    onDismissEditor: () -> Unit,
    onUpdateNode: (String, String, Map<String, String>) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier
            .fillMaxHeight()
            .background(Color(0x99000000))
            .border(width = 1.dp, color = Color(0x0FFFFFFF), shape = RoundedCornerShape(0.dp))
            .padding(16.dp),
    ) {
        // Summary header
        Text(
            "Summary",
            fontWeight = FontWeight.SemiBold,
            fontSize = 16.sp,
            color = Color.White,
            modifier = Modifier.padding(bottom = 6.dp).border(
                width = 0.dp,
                color = Color.Transparent,
            ),
        )
        HorizontalDivider(color = Color(0xFF60FAE5), thickness = 2.dp)
        Spacer(Modifier.height(8.dp))

        LazyColumn(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            // Topics
            val summary = graphData.summary
            if (summary.topics.isNotEmpty()) {
                item { SectionHeader("💡 Topics (${summary.topics.size})", Color(0xFF22C55E)) }
                items(summary.topics) { topic ->
                    SummaryCard(borderColor = Color(0xFF22C55E)) {
                        Text(topic.title, fontWeight = FontWeight.SemiBold, fontSize = 12.sp, color = Color(0xFFE5E7EB))
                        if (topic.summary.isNotBlank()) {
                            Text(topic.summary, fontSize = 11.sp, color = Color(0xFF9CA3AF), maxLines = 2, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
            }

            // Decisions
            if (summary.decisions.isNotEmpty()) {
                item { SectionHeader("⚖️ Decisions (${summary.decisions.size})", Color(0xFFF472B6)) }
                items(summary.decisions) { d ->
                    SummaryCard(borderColor = Color(0xFFF472B6)) {
                        Text(d.description, fontSize = 12.sp, color = Color(0xFFD1D5DB))
                    }
                }
            }

            // Tasks
            if (summary.tasks.isNotEmpty()) {
                item { SectionHeader("✅ Tasks (${summary.tasks.size})", Color(0xFFF59E0B)) }
                items(summary.tasks) { task ->
                    SummaryCard(borderColor = Color(0xFFF59E0B)) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(task.description, fontSize = 12.sp, color = Color(0xFFD1D5DB), modifier = Modifier.weight(1f), maxLines = 2)
                            Spacer(Modifier.width(4.dp))
                            TaskStatusBadge(task.status)
                        }
                        Text("${task.assignee} · ${task.deadline}", fontSize = 10.sp, color = Color(0xFF9CA3AF))
                    }
                }
            }

            // People
            if (summary.people.isNotEmpty()) {
                item { SectionHeader("👤 People (${summary.people.size})", Color(0xFFA855F7)) }
                items(summary.people) { p ->
                    SummaryCard(borderColor = Color(0xFFA855F7)) {
                        Text("${p.name}  ${p.role}", fontSize = 12.sp, color = Color(0xFFD1D5DB))
                    }
                }
            }

            // Entities (grouped)
            if (summary.entities.isNotEmpty()) {
                item { SectionHeader("🔗 Entities (${summary.entities.size})", Color(0xFFEC4899)) }
                val groups = summary.entities.groupBy { it.entityType }
                groups.forEach { (type, ents) ->
                    item {
                        Text(type.uppercase(), fontSize = 10.sp, color = Color(0xFF6B7280), fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp))
                    }
                    items(ents) { e ->
                        SummaryCard(borderColor = Color(0xFFEC4899)) {
                            Text(e.name, fontSize = 12.sp, color = Color(0xFFD1D5DB))
                            if (e.description.isNotBlank()) {
                                Text(e.description, fontSize = 10.sp, color = Color(0xFF9CA3AF), maxLines = 1)
                            }
                        }
                    }
                }
            }

            // Relations
            if (summary.relations.isNotEmpty()) {
                item { SectionHeader("↔️ Relations (${summary.relations.size})", Color(0xFFEC4899)) }
                items(summary.relations) { r ->
                    SummaryCard(borderColor = Color(0xFFEC4899)) {
                        Text(
                            "${r.source} —[${r.relationType}]→ ${r.target}",
                            fontSize = 11.sp, color = Color(0xFFD1D5DB),
                        )
                    }
                }
            }

            // Graph Schema
            item {
                Spacer(Modifier.height(8.dp))
                GraphSchemaPanel(graphData)
            }
        }

        // Node detail section
        if (selectedNodeId != null) {
            Spacer(Modifier.height(8.dp))
            HorizontalDivider(color = Color(0xFF333333))
            Spacer(Modifier.height(8.dp))
            NodeDetailCard(
                node = graphData.nodes.find { it.id == selectedNodeId },
                connectionCount = graphData.edges.count { it.from == selectedNodeId || it.to == selectedNodeId },
                onEditClick = onEditClick,
            )
        }
    }
}

// ── Node Detail Card ──

@Composable
private fun NodeDetailCard(
    node: GraphNode?,
    connectionCount: Int,
    onEditClick: () -> Unit,
) {
    if (node == null) return

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color(0x80000000), RoundedCornerShape(6.dp))
            .border(1.dp, Color(0x14FFFFFF), RoundedCornerShape(6.dp))
            .padding(10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "${node.type.icon} ${node.label}",
                fontWeight = FontWeight.SemiBold,
                fontSize = 14.sp,
                color = node.type.color,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            IconButton(onClick = onEditClick, modifier = Modifier.size(24.dp)) {
                Icon(Icons.Default.Edit, contentDescription = "Edit", tint = Color(0xFF60A5FA), modifier = Modifier.size(14.dp))
            }
        }
        Spacer(Modifier.height(4.dp))

        DetailField("Type", node.type.label, node.type.color)
        node.extra.forEach { (key, value) ->
            if (value.isNotBlank()) {
                if (key == "status") {
                    DetailField(key, value, TASK_STATUS_COLORS[value] ?: Color(0xFFE5E7EB))
                } else {
                    DetailField(key, value)
                }
            }
        }
        DetailField("Connections", connectionCount.toString())
    }
}

@Composable
private fun DetailField(label: String, value: String, valueColor: Color = Color(0xFFE5E7EB)) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp)
            .border(width = 0.dp, color = Color.Transparent),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, fontSize = 11.sp, color = Color(0xFF6B7280))
        Text(value, fontSize = 11.sp, color = valueColor, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
    HorizontalDivider(color = Color(0x0AFFFFFF))
}

// ── Graph Schema Panel ──

@Composable
private fun GraphSchemaPanel(graphData: GraphDisplayData) {
    Column {
        Text("Graph Schema", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF60FAE5))
        Spacer(Modifier.height(6.dp))

        // Node type badges
        Text("Node Types", fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF9CA3AF))
        Spacer(Modifier.height(4.dp))
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            NodeType.entries.forEach { type ->
                val count = graphData.nodes.count { it.type == type }
                if (count > 0) {
                    SchemaTypeBadge(type.label, type.color, count)
                }
            }
        }

        Spacer(Modifier.height(8.dp))

        // Statistics
        Text("Statistics", fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF9CA3AF))
        Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Nodes", fontSize = 10.sp, color = Color(0xFF9CA3AF))
            Text("${graphData.nodes.size}", fontSize = 10.sp, color = Color(0xFFE5E7EB))
        }
        Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Edges", fontSize = 10.sp, color = Color(0xFF9CA3AF))
            Text("${graphData.edges.size}", fontSize = 10.sp, color = Color(0xFFE5E7EB))
        }
    }
}

@Composable
private fun SchemaTypeBadge(label: String, color: Color, count: Int) {
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(Color(0x0AFFFFFF))
            .border(1.dp, Color(0x14FFFFFF), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Box(
            modifier = Modifier
                .size(7.dp)
                .clip(RoundedCornerShape(99.dp))
                .background(color),
        )
        Text("$label ($count)", fontSize = 10.sp, color = Color(0xFFE5E7EB))
    }
}

// ── Node Editor Dialog ──

@Composable
fun NodeEditorDialog(
    node: GraphNode,
    onDismiss: () -> Unit,
    onSave: (nodeType: String, nodeId: String, fields: Map<String, String>) -> Unit,
) {
    val editableFields = remember(node) {
        mutableStateMapOf<String, String>().apply {
            node.extra.forEach { (k, v) -> put(k, v) }
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text("${node.type.icon} 노드 편집 — ${node.label}", maxLines = 1, overflow = TextOverflow.Ellipsis)
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Type: ${node.type.label}", fontSize = 12.sp, color = Color(0xFF9CA3AF))
                editableFields.keys.sorted().forEach { key ->
                    if (key == "status") {
                        // Status dropdown
                        var expanded by remember { mutableStateOf(false) }
                        val statuses = listOf("pending", "in_progress", "done", "blocked")
                        ExposedDropdownMenuBox(
                            expanded = expanded,
                            onExpandedChange = { expanded = it },
                        ) {
                            OutlinedTextField(
                                value = editableFields[key] ?: "",
                                onValueChange = {},
                                readOnly = true,
                                label = { Text(key) },
                                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
                                modifier = Modifier.menuAnchor().fillMaxWidth(),
                            )
                            ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                                statuses.forEach { status ->
                                    DropdownMenuItem(
                                        text = { Text(status) },
                                        onClick = {
                                            editableFields[key] = status
                                            expanded = false
                                        },
                                    )
                                }
                            }
                        }
                    } else {
                        OutlinedTextField(
                            value = editableFields[key] ?: "",
                            onValueChange = { editableFields[key] = it },
                            label = { Text(key) },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                val nodeType = node.type.label
                onSave(nodeType, node.id, editableFields.toMap())
            }) {
                Text("저장")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("취소")
            }
        },
    )
}
