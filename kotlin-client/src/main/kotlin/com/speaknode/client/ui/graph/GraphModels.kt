package com.speaknode.client.ui.graph

import androidx.compose.ui.graphics.Color
import com.speaknode.client.api.models.*
import com.speaknode.client.util.ScopeUtils
import kotlinx.serialization.json.*
import kotlin.math.*
import kotlin.random.Random

// ── Node / Edge types (colors from index.html) ──

enum class NodeType(val color: Color, val glowColor: Color, val radius: Float, val icon: String, val label: String) {
    Meeting(Color(0xFF60A5FA), Color(0x4D60A5FA), 28f, "📅", "Meeting"),
    Person(Color(0xFFA855F7), Color(0x4DA855F7), 20f, "👤", "Person"),
    Topic(Color(0xFF22C55E), Color(0x4D22C55E), 18f, "💡", "Topic"),
    Task(Color(0xFFF59E0B), Color(0x4DF59E0B), 16f, "✅", "Task"),
    Decision(Color(0xFFF472B6), Color(0x4DF472B6), 16f, "⚖️", "Decision"),
    Utterance(Color(0xFF06B6D4), Color(0x3306B6D4), 10f, "💬", "Utterance"),
    Entity(Color(0xFFEC4899), Color(0x40EC4899), 14f, "🔗", "Entity"),
}

enum class EdgeType(val color: Color, val width: Float, val dashed: Boolean) {
    DISCUSSED(Color(0x8060A5FA), 2f, false),
    PROPOSED(Color(0x80A855F7), 2f, false),
    ASSIGNED_TO(Color(0x80F59E0B), 2f, true),
    RESULTED_IN(Color(0x80F472B6), 2f, false),
    SPOKE(Color(0x4D06B6D4), 1f, false),
    CONTAINS(Color(0x3360A5FA), 1f, true),
    HAS_TASK(Color(0x4DF59E0B), 1.5f, false),
    HAS_DECISION(Color(0x4DF472B6), 1.5f, false),
    NEXT(Color(0x2606B6D4), 1f, true),
    RELATED_TO(Color(0x59EC4899), 1.5f, true),
    MENTIONS(Color(0x4D22C55E), 1f, true),
    HAS_ENTITY(Color(0x40EC4899), 1f, false),
}

val TASK_STATUS_COLORS = mapOf(
    "pending" to Color(0xFFF59E0B),
    "in_progress" to Color(0xFF06B6D4),
    "done" to Color(0xFF22C55E),
    "blocked" to Color(0xFFEF4444),
)

// ── Data classes ──

data class GraphNode(
    val id: String,
    val label: String,
    val type: NodeType,
    val extra: Map<String, String> = emptyMap(),
)

data class GraphEdge(
    val from: String,
    val to: String,
    val type: EdgeType,
)

data class GraphDisplayData(
    val nodes: List<GraphNode>,
    val edges: List<GraphEdge>,
    val summary: GraphSummary,
)

data class GraphSummary(
    val topics: List<Topic> = emptyList(),
    val decisions: List<Decision> = emptyList(),
    val tasks: List<Task> = emptyList(),
    val people: List<Person> = emptyList(),
    val entities: List<EntityItem> = emptyList(),
    val relations: List<RelationItem> = emptyList(),
)

// ── Parsing: JsonObject (graph_dump) → GraphDisplayData ──

fun parseGraphDump(dump: JsonObject): GraphDisplayData {
    val nodesObj = dump["nodes"]?.jsonObject ?: return emptyGraphData()
    val edgesObj = dump["edges"]?.jsonObject ?: return emptyGraphData()

    val graphNodes = mutableListOf<GraphNode>()
    val graphEdges = mutableListOf<GraphEdge>()
    val idMap = mutableSetOf<String>()

    // Parse nodes
    nodesObj["meetings"]?.jsonArray?.forEach { m ->
        val o = m.jsonObject
        val id = o.str("id")
        if (id.isNotEmpty() && idMap.add(id)) {
            graphNodes += GraphNode(id, o.str("title"), NodeType.Meeting, mapOf(
                "date" to o.str("date"),
                "source_file" to o.str("source_file"),
            ))
        }
    }
    nodesObj["people"]?.jsonArray?.forEach { p ->
        val o = p.jsonObject
        val name = o.str("name")
        val id = "p_$name"
        if (name.isNotEmpty() && idMap.add(id)) {
            graphNodes += GraphNode(id, name, NodeType.Person, mapOf("role" to o.str("role")))
        }
    }
    nodesObj["topics"]?.jsonArray?.forEach { t ->
        val o = t.jsonObject
        val title = o.str("title")
        val id = "t_$title"
        if (title.isNotEmpty() && idMap.add(id)) {
            graphNodes += GraphNode(id, ScopeUtils.decode(title), NodeType.Topic, mapOf("summary" to o.str("summary")))
        }
    }
    nodesObj["tasks"]?.jsonArray?.forEach { t ->
        val o = t.jsonObject
        val desc = o.str("description")
        val id = "tk_$desc"
        if (desc.isNotEmpty() && idMap.add(id)) {
            graphNodes += GraphNode(id, ScopeUtils.decode(desc), NodeType.Task, mapOf(
                "deadline" to o.str("deadline"),
                "status" to o.str("status"),
            ))
        }
    }
    nodesObj["decisions"]?.jsonArray?.forEach { d ->
        val o = d.jsonObject
        val desc = o.str("description")
        val id = "d_$desc"
        if (desc.isNotEmpty() && idMap.add(id)) {
            graphNodes += GraphNode(id, ScopeUtils.decode(desc), NodeType.Decision)
        }
    }
    nodesObj["utterances"]?.jsonArray?.forEach { u ->
        val o = u.jsonObject
        val uid = o.str("id")
        val text = o.str("text")
        if (uid.isNotEmpty() && idMap.add(uid)) {
            val label = if (text.length > 25) text.take(25) + "…" else text
            graphNodes += GraphNode(uid, label, NodeType.Utterance, mapOf(
                "text" to text,
                "start" to o.str("start"),
                "end" to o.str("end"),
            ))
        }
    }
    nodesObj["entities"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        val name = o.str("name")
        val id = "e_$name"
        if (name.isNotEmpty() && idMap.add(id)) {
            graphNodes += GraphNode(id, ScopeUtils.decode(name), NodeType.Entity, mapOf(
                "entity_type" to o.str("entity_type"),
                "description" to o.str("description"),
            ))
        }
    }

    // Parse edges
    edgesObj["discussed"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge(o.str("meeting_id"), "t_" + o.str("topic"), EdgeType.DISCUSSED)
    }
    edgesObj["proposed"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge("p_" + o.str("person"), "t_" + o.str("topic"), EdgeType.PROPOSED)
    }
    edgesObj["assigned_to"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge("p_" + o.str("person"), "tk_" + o.str("task"), EdgeType.ASSIGNED_TO)
    }
    edgesObj["resulted_in"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge("t_" + o.str("topic"), "d_" + o.str("decision"), EdgeType.RESULTED_IN)
    }
    edgesObj["spoke"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge("p_" + o.str("person"), o.str("utterance_id"), EdgeType.SPOKE)
    }
    edgesObj["next"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge(o.str("from_utterance_id"), o.str("to_utterance_id"), EdgeType.NEXT)
    }
    edgesObj["contains"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge(o.str("meeting_id"), o.str("utterance_id"), EdgeType.CONTAINS)
    }
    edgesObj["has_task"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge(o.str("meeting_id"), "tk_" + o.str("task"), EdgeType.HAS_TASK)
    }
    edgesObj["has_decision"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge(o.str("meeting_id"), "d_" + o.str("decision"), EdgeType.HAS_DECISION)
    }
    edgesObj["related_to"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge("e_" + o.str("source"), "e_" + o.str("target"), EdgeType.RELATED_TO)
    }
    edgesObj["mentions"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge("t_" + o.str("topic"), "e_" + o.str("entity"), EdgeType.MENTIONS)
    }
    edgesObj["has_entity"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        graphEdges += GraphEdge(o.str("meeting_id"), "e_" + o.str("entity"), EdgeType.HAS_ENTITY)
    }

    // Build summary from graph nodes + edges
    val assigneeMap = mutableMapOf<String, String>()
    edgesObj["assigned_to"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        assigneeMap["tk_" + o.str("task")] = o.str("person")
    }
    val proposerMap = mutableMapOf<String, String>()
    edgesObj["proposed"]?.jsonArray?.forEach { e ->
        val o = e.jsonObject
        proposerMap["t_" + o.str("topic")] = o.str("person")
    }

    val summary = GraphSummary(
        topics = graphNodes.filter { it.type == NodeType.Topic }.map { n ->
            Topic(
                title = n.label,
                summary = n.extra["summary"] ?: "",
                proposer = proposerMap[n.id] ?: "Unknown",
            )
        },
        decisions = graphNodes.filter { it.type == NodeType.Decision }.map { n ->
            Decision(description = n.label)
        },
        tasks = graphNodes.filter { it.type == NodeType.Task }.map { n ->
            Task(
                description = n.label,
                assignee = assigneeMap[n.id] ?: "Unassigned",
                deadline = n.extra["deadline"] ?: "TBD",
                status = n.extra["status"] ?: "pending",
            )
        },
        people = graphNodes.filter { it.type == NodeType.Person }.map { n ->
            Person(name = n.label, role = n.extra["role"] ?: "Member")
        },
        entities = graphNodes.filter { it.type == NodeType.Entity }.map { n ->
            EntityItem(
                name = n.label,
                entityType = n.extra["entity_type"] ?: "concept",
                description = n.extra["description"] ?: "",
            )
        },
        relations = graphEdges.filter { it.type == EdgeType.RELATED_TO }.map { e ->
            val srcNode = graphNodes.find { it.id == e.from }
            val tgtNode = graphNodes.find { it.id == e.to }
            RelationItem(
                source = srcNode?.label ?: e.from,
                target = tgtNode?.label ?: e.to,
                relationType = "related_to",
            )
        },
    )

    return GraphDisplayData(graphNodes, graphEdges, summary)
}

private fun emptyGraphData() = GraphDisplayData(emptyList(), emptyList(), GraphSummary())
private fun JsonObject.str(key: String): String = this[key]?.jsonPrimitive?.content ?: ""

// ── Force-Directed Layout (Fruchterman-Reingold variant) ──

class LayoutNode(
    val node: GraphNode,
    var x: Float,
    var y: Float,
    var vx: Float = 0f,
    var vy: Float = 0f,
)

class ForceDirectedLayout(
    data: GraphDisplayData,
    showUtterances: Boolean = false,
) {
    val nodes: List<LayoutNode>
    val edges: List<GraphEdge>
    val nodeMap: Map<String, LayoutNode>

    private val repulsion = 8000f
    private val attraction = 0.04f
    private val springLength = 150f
    private val centerGravity = 0.005f
    private val damping = 0.5f

    var isStable = false
        private set

    init {
        val filteredNodes = if (showUtterances) data.nodes else data.nodes.filter { it.type != NodeType.Utterance }
        val nodeIds = filteredNodes.map { it.id }.toSet()
        edges = data.edges.filter { it.from in nodeIds && it.to in nodeIds }

        val rng = Random(42)
        nodes = filteredNodes.map { n ->
            LayoutNode(
                node = n,
                x = (rng.nextFloat() - 0.5f) * 600f,
                y = (rng.nextFloat() - 0.5f) * 400f,
            )
        }
        nodeMap = nodes.associateBy { it.node.id }
    }

    fun iterate() {
        if (isStable) return

        // Reset velocities
        nodes.forEach { it.vx = 0f; it.vy = 0f }

        // Repulsion between all node pairs
        for (i in nodes.indices) {
            for (j in i + 1 until nodes.size) {
                val a = nodes[i]
                val b = nodes[j]
                val dx = b.x - a.x
                val dy = b.y - a.y
                val dist = max(sqrt(dx * dx + dy * dy), 1f)
                val force = repulsion / (dist * dist)
                val fx = force * dx / dist
                val fy = force * dy / dist
                a.vx -= fx; a.vy -= fy
                b.vx += fx; b.vy += fy
            }
        }

        // Attraction along edges
        for (edge in edges) {
            val a = nodeMap[edge.from] ?: continue
            val b = nodeMap[edge.to] ?: continue
            val dx = b.x - a.x
            val dy = b.y - a.y
            val dist = max(sqrt(dx * dx + dy * dy), 1f)
            val force = attraction * (dist - springLength)
            val fx = force * dx / dist
            val fy = force * dy / dist
            a.vx += fx; a.vy += fy
            b.vx -= fx; b.vy -= fy
        }

        // Center gravity
        for (node in nodes) {
            node.vx -= centerGravity * node.x
            node.vy -= centerGravity * node.y
        }

        // Apply with damping, check stability
        var totalMovement = 0f
        for (node in nodes) {
            node.vx *= damping
            node.vy *= damping
            // Clamp max speed
            val speed = sqrt(node.vx * node.vx + node.vy * node.vy)
            if (speed > 50f) {
                node.vx = node.vx / speed * 50f
                node.vy = node.vy / speed * 50f
            }
            node.x += node.vx
            node.y += node.vy
            totalMovement += abs(node.vx) + abs(node.vy)
        }

        if (nodes.isNotEmpty() && totalMovement / nodes.size < 0.05f) {
            isStable = true
        }
    }
}
