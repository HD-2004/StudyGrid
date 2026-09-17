package com.studygrid.companion

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

class HealthSyncWorker(
    appContext: Context,
    parameters: WorkerParameters,
) : CoroutineWorker(appContext, parameters) {
    override suspend fun doWork(): Result {
        val store = SecretStore(applicationContext)
        val token = store.token() ?: return Result.success()
        val serverUrl = store.serverUrl.takeIf { it.isNotBlank() } ?: return Result.success()
        val reader = HealthConnectReader(applicationContext)
        if (reader.sdkStatus() != androidx.health.connect.client.HealthConnectClient.SDK_AVAILABLE) {
            return Result.retry()
        }
        if (!reader.hasBackgroundPermission() || !reader.hasCorePermissions()) {
            return Result.success()
        }
        return runCatching {
            val summaries = reader.readDaily(7)
            if (summaries.isNotEmpty()) {
                StudyGridApi().sync(serverUrl, token, summaries, reader.grantedPermissions())
            }
            Result.success()
        }.getOrElse { Result.retry() }
    }

    companion object {
        private const val UNIQUE_WORK = "studygrid-health-sync"

        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()
            val work = PeriodicWorkRequestBuilder<HealthSyncWorker>(24, TimeUnit.HOURS)
                .setConstraints(constraints)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                UNIQUE_WORK,
                ExistingPeriodicWorkPolicy.UPDATE,
                work,
            )
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(UNIQUE_WORK)
        }
    }
}
