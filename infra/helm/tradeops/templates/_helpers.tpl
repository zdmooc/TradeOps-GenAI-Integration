{{- define "tradeops.labels" -}}
app.kubernetes.io/part-of: tradeops
app.kubernetes.io/managed-by: {{ .Release.Service | quote }}
{{- end }}

{{- define "tradeops.podSecurityContext" -}}
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{- define "tradeops.containerSecurityContext" -}}
allowPrivilegeEscalation: false
capabilities:
  drop:
    - ALL
{{- end }}
