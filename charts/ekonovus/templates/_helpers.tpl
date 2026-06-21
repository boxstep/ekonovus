{{- define "ekonovus.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "ekonovus.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := .Chart.Name }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "ekonovus.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "ekonovus.labels" -}}
helm.sh/chart: {{ include "ekonovus.chart" . }}
{{ include "ekonovus.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "ekonovus.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ekonovus.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
