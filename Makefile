MODULE := github.com/adrimg3196/lucidfence
VERSION ?= 2.0.0-dev
COMMIT ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
LDFLAGS := -s -w -X $(MODULE)/internal/version.Version=$(VERSION) -X $(MODULE)/internal/version.Commit=$(COMMIT)

.DEFAULT_GOAL := verify

.PHONY: build web lint test cover battery verify clean

web:
	cd web && npm ci && npm run build

build:
	CGO_ENABLED=0 go build -trimpath -ldflags '$(LDFLAGS)' -o bin/lucidfence ./cmd/lucidfence

lint:
	gofmt -l cmd internal | tee /dev/stderr | test -z "$$(cat)"
	go vet ./...
	golangci-lint run ./...

test:
	go test -race -count=1 ./...

cover:
	scripts/coverage.sh

battery: web build
	scripts/battery.sh bin/lucidfence

verify: lint cover web battery
	@echo "verify: OK"

clean:
	rm -rf bin coverage.out test.out
