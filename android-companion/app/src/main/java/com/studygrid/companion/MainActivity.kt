package com.studygrid.companion

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val store = SecretStore(this)
        val reader = HealthConnectReader(this)
        val api = StudyGridApi()
        setContent {
            StudyGridTheme {
                CompanionScreen(
                    appContext = applicationContext,
                    store = store,
                    reader = reader,
                    api = api,
                    openHealthConnect = { openHealthConnectStore() },
                )
            }
        }
    }

    private fun openHealthConnectStore() {
        startActivity(
            Intent(Intent.ACTION_VIEW).apply {
                data = Uri.parse("market://details?id=com.google.android.apps.healthdata")
                setPackage("com.android.vending")
            },
        )
    }
}

@Composable
private fun CompanionScreen(
    appContext: android.content.Context,
    store: SecretStore,
    reader: HealthConnectReader,
    api: StudyGridApi,
    openHealthConnect: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val sdkStatus = remember { reader.sdkStatus() }
    var serverUrl by rememberSaveable { mutableStateOf(store.serverUrl) }
    var pairingCode by rememberSaveable { mutableStateOf("") }
    var connected by remember { mutableStateOf(store.hasToken) }
    var permissionsGranted by remember { mutableStateOf(false) }
    var backgroundGranted by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf("Sẵn sàng ghép nối với kế hoạch StudyGrid của bạn.") }
    var isError by remember { mutableStateOf(false) }
    var disclosureAccepted by rememberSaveable { mutableStateOf(false) }

    val permissionLauncher = rememberLauncherForActivityResult(
        PermissionController.createRequestPermissionResultContract(),
    ) { granted ->
        permissionsGranted = granted.containsAll(reader.corePermissions)
        backgroundGranted = androidx.health.connect.client.permission.HealthPermission
            .PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND in granted
        isError = !permissionsGranted
        message = if (permissionsGranted) {
            if (backgroundGranted) "Đã cấp quyền. Có thể đồng bộ nền mỗi ngày."
            else "Đã cấp quyền chỉ khi ứng dụng mở. Bạn vẫn có thể đồng bộ thủ công."
        } else {
            "Bạn có thể chọn quyền, nhưng cần Sleep, Resting heart rate và HRV để đồng bộ đầy đủ."
        }
    }

    LaunchedEffect(sdkStatus) {
        if (sdkStatus == HealthConnectClient.SDK_AVAILABLE) {
            permissionsGranted = runCatching { reader.hasCorePermissions() }.getOrDefault(false)
            backgroundGranted = runCatching { reader.hasBackgroundPermission() }.getOrDefault(false)
        }
    }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp, vertical = 28.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(42.dp)
                        .background(Mint.copy(alpha = .16f), RoundedCornerShape(12.dp)),
                    contentAlignment = Alignment.Center,
                ) { Text("SG", color = Mint, fontWeight = FontWeight.Black) }
                Column(modifier = Modifier.padding(start = 12.dp)) {
                    Text("StudyGrid Companion", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Text("Health Connect · Android", color = InkSoft, fontSize = 12.sp)
                }
            }

            StatusCard(
                connected = connected,
                permissionsGranted = permissionsGranted,
                backgroundGranted = backgroundGranted,
            )

            if (sdkStatus != HealthConnectClient.SDK_AVAILABLE) {
                Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Health Connect chưa sẵn sàng", fontWeight = FontWeight.Bold)
                        Text(
                            "Android 14 có Health Connect trong hệ thống. Android 9–13 cần cài hoặc cập nhật ứng dụng Health Connect.",
                            color = InkSoft,
                            fontSize = 13.sp,
                        )
                        Button(onClick = openHealthConnect) { Text("Mở Google Play") }
                    }
                }
            } else {
                Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionLabel("1 · Ghép nối")
                        Text("Nhập địa chỉ API và mã một lần từ Tiến độ → Sức khỏe trên web.", color = InkSoft, fontSize = 13.sp)
                        OutlinedTextField(
                            value = serverUrl,
                            onValueChange = { serverUrl = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("StudyGrid API URL") },
                            placeholder = { Text("https://studygrid.example.com") },
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = pairingCode,
                            onValueChange = { pairingCode = it.uppercase().take(9) },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("Mã ghép nối") },
                            placeholder = { Text("ABCD-EFGH") },
                            singleLine = true,
                            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters),
                        )
                        Button(
                            onClick = {
                                scope.launch {
                                    busy = true
                                    isError = false
                                    runCatching { api.claim(serverUrl, pairingCode) }
                                        .onSuccess {
                                            store.saveConnection(serverUrl, it.accessToken)
                                            serverUrl = store.serverUrl
                                            connected = true
                                            pairingCode = ""
                                            message = "Đã ghép nối. Token được mã hóa bằng Android Keystore."
                                        }
                                        .onFailure {
                                            isError = true
                                            message = it.message ?: "Không thể ghép nối."
                                        }
                                    busy = false
                                }
                            },
                            enabled = !busy && serverUrl.isNotBlank() && pairingCode.replace("-", "").length == 8,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(if (busy) "Đang ghép nối…" else "Ghép nối") }
                    }
                }

                Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionLabel("2 · Quyền riêng tư")
                        Text(
                            "StudyGrid đọc thời lượng ngủ, nhịp tim nghỉ và HRV trong 7 ngày. Chỉ tổng hợp theo ngày được gửi; mẫu nhịp tim thô không rời thiết bị.",
                            color = InkSoft,
                            fontSize = 13.sp,
                            lineHeight = 19.sp,
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = disclosureAccepted, onCheckedChange = { disclosureAccepted = it })
                            Text("Tôi hiểu đây là hướng dẫn wellness, không phải chẩn đoán y tế.", fontSize = 12.sp)
                        }
                        OutlinedButton(
                            onClick = { permissionLauncher.launch(reader.requestedPermissions) },
                            enabled = disclosureAccepted,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(if (permissionsGranted) "Xem lại quyền Health Connect" else "Cấp quyền Health Connect") }
                    }
                }

                Card(colors = CardDefaults.cardColors(containerColor = Panel)) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        SectionLabel("3 · Đồng bộ")
                        Text("Đồng bộ thủ công bất cứ lúc nào. Đồng bộ nền chỉ bật khi Android đã cấp quyền nền.", color = InkSoft, fontSize = 13.sp)
                        Button(
                            onClick = {
                                scope.launch {
                                    busy = true
                                    isError = false
                                    runCatching {
                                        val token = store.token() ?: error("Hãy ghép nối trước.")
                                        val summaries = reader.readDaily(7)
                                        if (summaries.isEmpty()) error("Không tìm thấy dữ liệu trong 7 ngày gần đây.")
                                        val accepted = api.sync(
                                            store.serverUrl,
                                            token,
                                            summaries,
                                            reader.grantedPermissions(),
                                        )
                                        if (reader.hasBackgroundPermission()) {
                                            HealthSyncWorker.schedule(appContext)
                                        }
                                        accepted
                                    }.onSuccess {
                                        message = "Đã đồng bộ $it ngày tổng hợp với StudyGrid."
                                    }.onFailure {
                                        isError = true
                                        message = it.message ?: "Không thể đồng bộ."
                                    }
                                    busy = false
                                }
                            },
                            enabled = !busy && connected && permissionsGranted,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(if (busy) "Đang đồng bộ…" else "Đồng bộ ngay") }
                        OutlinedButton(
                            onClick = {
                                HealthSyncWorker.cancel(appContext)
                                store.clearConnection()
                                connected = false
                                message = "Đã xóa token trên điện thoại. Hãy ngắt kết nối trên web để xóa dữ liệu máy chủ."
                            },
                            enabled = connected,
                            modifier = Modifier.fillMaxWidth(),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Coral),
                        ) { Text("Xóa kết nối trên điện thoại") }
                    }
                }
            }

            Card(colors = CardDefaults.cardColors(containerColor = if (isError) Coral.copy(alpha = .12f) else Mint.copy(alpha = .10f))) {
                Text(message, modifier = Modifier.padding(14.dp), color = if (isError) Coral else Ink, fontSize = 12.sp)
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
private fun StatusCard(connected: Boolean, permissionsGranted: Boolean, backgroundGranted: Boolean) {
    Card(colors = CardDefaults.cardColors(containerColor = PanelStrong)) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Trạng thái", color = InkSoft, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            StatusRow("Kế hoạch StudyGrid", if (connected) "Đã ghép nối" else "Chưa ghép nối", connected)
            HorizontalDivider(color = Rule)
            StatusRow("Quyền Health Connect", if (permissionsGranted) "Đã cấp" else "Chưa cấp", permissionsGranted)
            HorizontalDivider(color = Rule)
            StatusRow("Đồng bộ nền", if (backgroundGranted) "Mỗi ngày" else "Tắt", backgroundGranted)
        }
    }
}

@Composable
private fun StatusRow(label: String, value: String, active: Boolean) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(label, color = InkSoft, fontSize = 12.sp)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(7.dp).background(if (active) Mint else Muted, RoundedCornerShape(50)))
            Text(value, modifier = Modifier.padding(start = 7.dp), color = Ink, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun SectionLabel(value: String) {
    Text(value.uppercase(), color = Mint, fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
}

private val Background = Color(0xFF101715)
private val Panel = Color(0xFF17211E)
private val PanelStrong = Color(0xFF1C2925)
private val Mint = Color(0xFF7BE0B5)
private val Coral = Color(0xFFFF826D)
private val Ink = Color(0xFFE9F2EE)
private val InkSoft = Color(0xFFAABBB4)
private val Muted = Color(0xFF65756E)
private val Rule = Color(0xFF2C3B36)

@Composable
private fun StudyGridTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Mint,
            onPrimary = Color(0xFF0B1E16),
            background = Background,
            onBackground = Ink,
            surface = Panel,
            onSurface = Ink,
            outline = Rule,
            error = Coral,
        ),
        content = content,
    )
}
