package com.speaknode.client.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val SpeakNodeDark = darkColorScheme(
    primary = Color(0xFF7C4DFF),        // 보라색 포인트
    onPrimary = Color.White,
    secondary = Color(0xFF00E676),       // 녹색 보조
    onSecondary = Color.Black,
    surface = Color(0xFF1E1E1E),
    onSurface = Color(0xFFE0E0E0),
    background = Color(0xFF121212),
    onBackground = Color(0xFFE0E0E0),
    error = Color(0xFFCF6679),
    surfaceVariant = Color(0xFF2D2D2D),
    outline = Color(0xFF444444),
)

private val SpeakNodeTypography = Typography(
    headlineLarge = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 28.sp,
    ),
    headlineMedium = TextStyle(
        fontWeight = FontWeight.SemiBold,
        fontSize = 22.sp,
    ),
    titleMedium = TextStyle(
        fontWeight = FontWeight.Medium,
        fontSize = 16.sp,
    ),
    bodyMedium = TextStyle(
        fontSize = 14.sp,
        lineHeight = 22.sp,
    ),
    labelMedium = TextStyle(
        fontSize = 12.sp,
        color = Color(0xFF9E9E9E),
    ),
)

@Composable
fun SpeakNodeTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = SpeakNodeDark,
        typography = SpeakNodeTypography,
        content = content,
    )
}
