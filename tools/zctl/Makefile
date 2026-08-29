.PHONY: all build test vet clean lint

# Default target
all: vet test build

build:
	@echo "==> Building zctl..."
	go build -o ../../bin/zctl ./cmd/zctl

test:
	@echo "==> Running tests..."
	go test ./...

vet:
	@echo "==> Running go vet..."
	go vet ./...

clean:
	@echo "==> Cleaning up..."
	rm -f ../../bin/zctl
	go clean

lint:
	@echo "==> Running linter..."
	go fmt ./...
