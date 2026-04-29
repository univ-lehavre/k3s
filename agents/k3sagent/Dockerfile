FROM golang:1.23-alpine AS build

WORKDIR /src
COPY agents/k3sagent/go.mod ./
COPY agents/k3sagent/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/k3sagent ./cmd/k3sagent

FROM scratch

COPY --from=build /out/k3sagent /k3sagent
ENTRYPOINT ["/k3sagent"]
