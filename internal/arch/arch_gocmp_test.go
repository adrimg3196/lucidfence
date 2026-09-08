package arch

import (
	"go/parser"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func goCmpProductionImport(name string, source []byte) (bool, error) {
	f, err := parser.ParseFile(token.NewFileSet(), name, source, parser.ImportsOnly)
	if err != nil {
		return false, err
	}
	if strings.HasSuffix(name, "_test.go") {
		return false, nil
	}
	for _, imp := range f.Imports {
		path, err := strconv.Unquote(imp.Path.Value)
		if err != nil {
			return false, err
		}
		if path == "github.com/google/go-cmp" || strings.HasPrefix(path, "github.com/google/go-cmp/") {
			return true, nil
		}
	}
	return false, nil
}

func TestProductionDoesNotImportGoCmp(t *testing.T) {
	root := repoRoot(t)
	for _, dir := range []string{"cmd", "internal"} {
		err := filepath.WalkDir(filepath.Join(root, dir), func(path string, entry fs.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if entry.IsDir() || !strings.HasSuffix(path, ".go") {
				return nil
			}
			source, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			denied, err := goCmpProductionImport(path, source)
			if err != nil {
				return err
			}
			if denied {
				t.Errorf("go-cmp solo se permite en tests: %s", path)
			}
			return nil
		})
		if err != nil {
			t.Fatal(err)
		}
	}
}

func TestGoCmpOnlyTestImports(t *testing.T) {
	for _, tc := range []struct {
		name, source string
		denied       bool
	}{
		{"prod.go", `package p; import "github.com/google/go-cmp/cmp"`, true},
		{"prod.go", `package p; import c "github.com/google/go-cmp/cmp/cmpopts"`, true},
		{"prod.go", `package p; import _ "github.com/google/go-cmp"`, true},
		{"prod_test.go", `package p; import "github.com/google/go-cmp/cmp"`, false},
		{"prod.go", `package p; import "math"`, false},
	} {
		denied, err := goCmpProductionImport(tc.name, []byte(tc.source))
		if err != nil || denied != tc.denied {
			t.Errorf("%s %s denied=%v err=%v", tc.name, tc.source, denied, err)
		}
	}
}
