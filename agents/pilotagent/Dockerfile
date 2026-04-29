FROM golang:1.23-alpine AS build

WORKDIR /src
COPY agents/pilotagent/go.mod ./
COPY agents/pilotagent/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/pilotagent ./cmd/pilotagent

FROM scratch

COPY --from=build /out/pilotagent /pilotagent
ENTRYPOINT ["/pilotagent"]
