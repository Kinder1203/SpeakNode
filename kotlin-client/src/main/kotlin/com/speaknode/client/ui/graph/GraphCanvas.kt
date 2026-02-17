package com.speaknode.client.ui.graph

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.PointerEventType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlin.math.*

/**
 * Interactive Knowledge Graph visualization using Compose Canvas.
 * Force-directed layout with zoom, pan, and node selection.
 * Styled after index.html's vis-network graph.
 */
@Composable
fun GraphCanvas(
    data: GraphDisplayData,
    showUtterances: Boolean,
    selectedNodeId: String?,
    onNodeClick: (String?) -> Unit,
    modifier: Modifier = Modifier,
) {
    var offset by remember { mutableStateOf(Offset.Zero) }
    var scale by remember { mutableFloatStateOf(1f) }
    var layoutTick by remember { mutableIntStateOf(0) }

    // Create layout instance (recreated when data or filter changes)
    val layout = remember(data, showUtterances) {
        ForceDirectedLayout(data, showUtterances)
    }

    // Run physics simulation
    LaunchedEffect(layout) {
        repeat(350) {
            if (layout.isStable) return@LaunchedEffect
            layout.iterate()
            layoutTick++
            delay(16)
        }
    }

    val textMeasurer = rememberTextMeasurer()

    Canvas(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFF0A0A0A))
            // Zoom with scroll wheel
            .pointerInput(Unit) {
                awaitPointerEventScope {
                    while (true) {
                        val event = awaitPointerEvent()
                        if (event.type == PointerEventType.Scroll) {
                            val change = event.changes.firstOrNull() ?: continue
                            val delta = change.scrollDelta.y
                            val zoomFactor = if (delta > 0) 0.9f else 1.1f
                            scale = (scale * zoomFactor).coerceIn(0.1f, 5f)
                            change.consume()
                        }
                    }
                }
            }
            // Pan with drag
            .pointerInput(Unit) {
                detectDragGestures { change, dragAmount ->
                    offset += dragAmount
                    change.consume()
                }
            }
            // Click to select node
            .pointerInput(layout, scale, offset) {
                detectTapGestures { tapOffset ->
                    val cx = size.width / 2f + offset.x
                    val cy = size.height / 2f + offset.y
                    val worldX = (tapOffset.x - cx) / scale
                    val worldY = (tapOffset.y - cy) / scale

                    val clickedNode = layout.nodes.firstOrNull { node ->
                        val dx = worldX - node.x
                        val dy = worldY - node.y
                        sqrt(dx * dx + dy * dy) < node.node.type.radius + 5f
                    }
                    onNodeClick(clickedNode?.node?.id)
                }
            },
    ) {
        // Read layoutTick to trigger re-draw on layout updates
        @Suppress("UNUSED_EXPRESSION")
        layoutTick

        val cx = size.width / 2f + offset.x
        val cy = size.height / 2f + offset.y

        // Draw edges
        for (edge in layout.edges) {
            val from = layout.nodeMap[edge.from] ?: continue
            val to = layout.nodeMap[edge.to] ?: continue

            val x1 = from.x * scale + cx
            val y1 = from.y * scale + cy
            val x2 = to.x * scale + cx
            val y2 = to.y * scale + cy

            val pathEffect = if (edge.type.dashed) {
                PathEffect.dashPathEffect(floatArrayOf(5f * scale, 5f * scale))
            } else null

            drawLine(
                color = edge.type.color,
                start = Offset(x1, y1),
                end = Offset(x2, y2),
                strokeWidth = edge.type.width * scale,
                pathEffect = pathEffect,
            )

            // Arrowhead
            drawArrowhead(x1, y1, x2, y2, edge.type.color, scale, to.node.type.radius)
        }

        // Draw nodes
        for (layoutNode in layout.nodes) {
            val node = layoutNode.node
            val x = layoutNode.x * scale + cx
            val y = layoutNode.y * scale + cy
            val r = node.type.radius * scale
            val isSelected = node.id == selectedNodeId

            // Glow
            drawCircle(
                color = node.type.glowColor,
                radius = r + 4f * scale,
                center = Offset(x, y),
            )

            // Fill
            drawCircle(
                color = if (isSelected) Color.White else node.type.color.copy(alpha = 0.8f),
                radius = r,
                center = Offset(x, y),
            )

            // Border
            drawCircle(
                color = node.type.color,
                radius = r,
                center = Offset(x, y),
                style = Stroke(width = if (isSelected) 2.5f * scale else 1.5f * scale),
            )

            // Label (only if zoomed in enough)
            if (scale > 0.3f) {
                val labelText = if (scale > 0.6f) {
                    "${node.type.icon} ${node.label}"
                } else {
                    node.label.take(10)
                }
                val fontSize = (9f * scale).coerceIn(6f, 14f)
                val maxWidth = (120f * scale).toInt().coerceAtLeast(30)

                val textResult = textMeasurer.measure(
                    text = labelText,
                    style = TextStyle(
                        fontSize = fontSize.sp,
                        color = Color(0xFFE5E7EB),
                    ),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    constraints = Constraints(maxWidth = maxWidth),
                )
                drawText(
                    textLayoutResult = textResult,
                    topLeft = Offset(
                        x - textResult.size.width / 2f,
                        y + r + 2f * scale,
                    ),
                )
            }
        }

        // Status text at bottom
        val statusText = "Nodes: ${layout.nodes.size} | Edges: ${layout.edges.size}"
        val statusResult = textMeasurer.measure(
            text = statusText,
            style = TextStyle(fontSize = 11.sp, color = Color(0xFF4B5563)),
        )
        drawText(
            textLayoutResult = statusResult,
            topLeft = Offset(8f, size.height - statusResult.size.height - 8f),
        )
    }
}

/**
 * Draw an arrowhead at the endpoint of an edge.
 */
private fun DrawScope.drawArrowhead(
    x1: Float, y1: Float,
    x2: Float, y2: Float,
    color: Color,
    scale: Float,
    targetRadius: Float,
) {
    val dx = x2 - x1
    val dy = y2 - y1
    val dist = sqrt(dx * dx + dy * dy)
    if (dist < 1f) return

    // Arrow tip positioned at the edge of the target node
    val targetR = targetRadius * scale
    val tipX = x2 - (dx / dist) * targetR
    val tipY = y2 - (dy / dist) * targetR

    val arrowLen = 8f * scale
    val arrowWidth = 4f * scale

    val angle = atan2(dy, dx)
    val sin = sin(angle)
    val cos = cos(angle)

    val p1x = tipX - arrowLen * cos + arrowWidth * sin
    val p1y = tipY - arrowLen * sin - arrowWidth * cos
    val p2x = tipX - arrowLen * cos - arrowWidth * sin
    val p2y = tipY - arrowLen * sin + arrowWidth * cos

    val path = androidx.compose.ui.graphics.Path().apply {
        moveTo(tipX, tipY)
        lineTo(p1x, p1y)
        lineTo(p2x, p2y)
        close()
    }
    drawPath(path, color)
}
