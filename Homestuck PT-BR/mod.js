module.exports = {
  title: "Homestuck PT-BR", 
  summary: "Uma história sobre um garoto, seus amigos e um jogo que eles jogam juntos. A quarta e última comic do MS Paint Adventures, produzida por Andrew Hussie, agora 100% traduzida e completa em português brasileiro para The Unofficial Homestuck Collection! Cobre todos os Atos de 1 a 7 e Créditos (mais de 8.000 páginas).",
  author: "Adok Caulifla (@PudinDiPreda / William José Barreto), TataEvans, anaSleuth, Equipe Homestuck BR",
  modVersion: "2.5",

  edit: true,

  trees: {
    "./Assets/": "assets://"
  },

  vueHooks: [{
    matchName: "pageText",
    computed: {
      logButtonText() {
        let text = this.content.match(/\|(.*?)\|/)[1]
        const state = (this.logHidden) ? 'Abrir ' : 'Fechar '
        if (/P4SSWORD H1NT/i.test(text)){
            return text
        }
        else if (/trkstrlog/i.test(text)){
            text = 'tricksterlog'
        }
        else if (/sriousbiz/i.test(text)){
            text = 'serious business'
        }
        return state + text.toLowerCase()
      }
    }
  }],

  computed(api) {
    const translation = api.readJson('./translation2.json')
    api.logger.info(`Carregando tradução Homestuck PT-BR: ${Object.keys(translation).length} páginas traduzidas.`)
    
    return {
      edit(archive) {
        for (const page_num in translation) {
          archive.mspa.story[page_num] = {
            ...archive.mspa.story[page_num],
            ...translation[page_num]
          }
        }
      }
    }
  }
}
