// Configuração dinâmica da API (Localhost x Vercel/Produção)
const isLocalhost =
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1" ||
    window.location.protocol === "file:";

const prodApiBase = (window.ATMOS_CONFIG && window.ATMOS_CONFIG.PROD_API_URL) || "https://atmos-jio7.onrender.com";
const localApiBase = (window.ATMOS_CONFIG && window.ATMOS_CONFIG.LOCAL_API_URL) || "http://127.0.0.1:8000";

let backendBase = (window.ATMOS_CONFIG && window.ATMOS_CONFIG.LOCAL_API_URL)
    ? (isLocalhost ? localApiBase : prodApiBase)
    : (isLocalhost ? "http://127.0.0.1:8000" : prodApiBase);

let API_URL = `${backendBase.replace(/\/+$/, "")}/api`;


/*configurações*/

const REGRAS_ALERTAS = {
    quedaPressao: { limite: 6 },
    qualidadeAr: { limite: 100 },
    calorSeco: { temperatura: 35, umidade: 30 },
    ondaCalor: { temperatura: 35, leituras: 3 },
    seca: { chuvaMaxima: 1, leituras: 7 }
};

let dadosAtuais = null;
let historico = [];
let alertas = [];
const graficos = {};

/*mapa*/

let mapa = null;
let marcadorEstacao = null;

/*funçoes auxilires*/

function pegarElemento(id) {
    return document.getElementById(id);
}

function texto(id, valor) {
    const elemento = pegarElemento(id);

    if (elemento) {
        elemento.textContent = valor;
    }
}

function mostrar(id, mostrar = true) {
    const elemento = pegarElemento(id);

    if (elemento) {
        if (mostrar) {
            elemento.style.display = "";
        } else {
            elemento.style.display = "none";
        }
    }
}

function numero(valor, casas = 1) {
    const numero = Number(valor);

    if (Number.isFinite(numero)) {
        return numero.toFixed(casas);
    }

    return "--";
}

function formatarDataHora(data) {
    if (!data) {
        return "--";
    }

    const dataFormatada = new Date(data);

    if (Number.isNaN(dataFormatada.getTime())) {
        return "--";
    }

    return dataFormatada.toLocaleString("pt-BR", {
        dateStyle: "short",
        timeStyle: "short"
    });
}

function formatarHora(data) {
    if (!data) {
        return "--";
    }

    const dataFormatada = new Date(data);

    if (Number.isNaN(dataFormatada.getTime())) {
        return "--";
    }

    return dataFormatada.toLocaleTimeString("pt-BR", {
        hour: "2-digit",
        minute: "2-digit"
    });
}

async function buscarJSON(url) {
    const separador = url.includes("?") ? "&" : "?";
    const urlComBuster = `${url}${separador}_t=${Date.now()}`;
    const opcoes = {
        cache: "no-store",
        headers: {
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    };
    try {
        const resposta = await fetch(urlComBuster, opcoes);

        if (!resposta.ok) {
            throw new Error(`Erro HTTP ${resposta.status}`);
        }

        return await resposta.json();
    } catch (erro) {
        // Fallback automático inteligente: se o localhost:8000 estiver fechado, busca direto do Render
        if ((url.includes("127.0.0.1:8000") || url.includes("localhost:8000")) && prodApiBase) {
            const fallbackUrl = urlComBuster.replace(/https?:\/\/(127\.0\.0\.1|localhost):8000/, prodApiBase.replace(/\/+$/, ""));
            console.warn(`[ATMOS] Backend local indisponível. Alternando automaticamente para o Render: ${fallbackUrl}`);
            try {
                const respostaFallback = await fetch(fallbackUrl, opcoes);
                if (respostaFallback.ok) {
                    backendBase = prodApiBase;
                    API_URL = `${backendBase.replace(/\/+$/, "")}/api`;
                    return await respostaFallback.json();
                }
            } catch (errFallback) {
                console.error("[ATMOS] Fallback para Render também falhou:", errFallback);
            }
        }
        throw erro;
    }
}

/*inicialização do mapa*/

function inicializarMapa() {
    const elemento = pegarElemento("mapaEstacao");

    if (!elemento) {
        console.warn("Elemento #mapaEstacao não encontrado.");
        return;
    }

    if (typeof L === "undefined") {
        console.error("Leaflet não foi carregado. Verifique o <script> do Leaflet no HTML.");
        return;
    }

    if (mapa) {
        return;
    }

    /*
     * Coordenadas iniciais.
     *
     * São usadas somente enquanto a API ainda não
     * forneceu a localização real da estação.
     */

    const coordenadasIniciais = [-23.5505, -46.6333];

    mapa = L.map(elemento).setView(
        coordenadasIniciais,
        13
    );

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            attribution: "&copy; OpenStreetMap contributors",
            maxZoom: 19
        }
    ).addTo(mapa);
}

function atualizarMapa(latitude, longitude) {
    if (!mapa) {
        return;
    }

    latitude = Number(latitude);
    longitude = Number(longitude);

    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
        return;
    }

    const coordenadas = [latitude, longitude];

    /* Cria o marcador apenas uma vez e muda a posição de acordo com as coordenadas */

    if (!marcadorEstacao) {
        marcadorEstacao = L.marker(coordenadas).addTo(mapa);
    } else {
        marcadorEstacao.setLatLng(coordenadas);
    }

    atualizarPopupMapa();

    /*centraliza mapa*/

    mapa.setView(
        coordenadas,
        15
    );
}

function atualizarPopupMapa() {
    if (!marcadorEstacao || !dadosAtuais) {
        return;
    }

    const temperatura = numero(dadosAtuais.temperatura);
    const umidade = numero(dadosAtuais.umidade);
    const pressao = numero(dadosAtuais.pressao);

    const local = dadosAtuais.localizacao ||
        dadosAtuais.local ||
        "Estação meteorológica";

    marcadorEstacao.bindPopup(`
        <div>
            <strong>Estação ATMOS</strong>
            <br>
            <span>${local}</span>
            <hr>
            <div>${temperatura} °C</div>
            <div>${umidade} %</div>
            <div>${pressao} hPa</div>
        </div>
    `);
}

/*tema*/

function atualizarTema() {
    const escuro = document.body.classList.contains("tema-escuro");
    const icone = pegarElemento("iconeTema");

    if (icone) {
        const imagem = icone.querySelector("img");

        if (imagem) {
            if (escuro) {
                imagem.src = "img/sol.png";
            } else {
                imagem.src = "img/lua.png";
            }

            imagem.alt = "";
        }
    }

    if (escuro) {
        texto("textoTema", "Tema claro");
    } else {
        texto("textoTema", "Tema escuro");
    }

    const botao = pegarElemento("botaoTema");

    if (botao) {
        if (escuro) {
            botao.setAttribute("aria-label", "Ativar tema claro");
        } else {
            botao.setAttribute("aria-label", "Ativar tema escuro");
        }

        botao.setAttribute("aria-pressed", String(escuro));
    }

    atualizarCoresGraficos();
}

function alternarTema() {
    document.body.classList.toggle("tema-escuro");
    atualizarTema();
}

const botaoTema = pegarElemento("botaoTema");

if (botaoTema) {
    botaoTema.addEventListener("click", alternarTema);
}

/*status da estação*/

function atualizarStatusEstacao(online = true) {
    const status = pegarElemento("statusEstacao");

    if (!status) {
        return;
    }

    if (online) {
        status.textContent = "Online";
    } else {
        status.textContent = "Offline";
    }

    status.classList.toggle("offline", !online);
    status.classList.toggle("online", online);
}

function atualizarStatusSensor(id, conectado) {
    const elemento = pegarElemento(id);

    if (!elemento) {
        return;
    }

    if (!elemento.dataset.textoBase) {
        elemento.dataset.textoBase = elemento.textContent
            .replace(/ conectado| desconectado/g, "")
            .trim();
    }

    if (conectado) {
        elemento.textContent =
            elemento.dataset.textoBase + " conectado";
    } else {
        elemento.textContent =
            elemento.dataset.textoBase + " desconectado";
    }

    elemento.classList.toggle("offline", !conectado);
    elemento.classList.toggle("online", conectado);
}

/*dados atuais*/

function atualizarDadosAtuais(dados) {
    dadosAtuais = dados;

    const valorGas = dados.qualidadeAr !== undefined ? dados.qualidadeAr : dados.qualidade_ar;
    const chovendo = Number(dados.chuva) > 0 || dados.chuva === true;

    // 1. Destaque principal
    texto("temperaturaDestaque", `${numero(dados.temperatura)} °C`);
    texto("statusChuvaTexto", chovendo ? "🌧️ Chuva detectada" : "☀️ Sem chuva no momento");
    texto("chuvaResumo", chovendo ? "Chuva detectada" : "Sem chuva");

    // 2. Cards de métricas
    texto("temperatura", numero(dados.temperatura));
    texto("umidade", numero(dados.umidade));
    texto("pressao", numero(dados.pressao));
    texto("luminosidade", numero(dados.luminosidade));
    texto("chuva", chovendo ? "Sim" : "Não");
    texto("qualidadeAr", numero(valorGas));

    texto("temperaturaInfo", "Temperatura atual da estação");
    texto("umidadeInfo", "Umidade relativa atual");
    texto("pressaoInfo", "Pressão atmosférica atual");
    texto("luminosidadeInfo", "Luminosidade atual");
    texto("chuvaInfo", chovendo ? "Chuva registrada" : "Sem chuva");
    texto("qualidadeArInfo", "Qualidade do ar atual");

    texto(
        "graficoTemperaturaAtual",
        `${numero(dados.temperatura)}°C`
    );

    texto(
        "graficoUmidadeAtual",
        `${numero(dados.umidade)}%`
    );

    texto(
        "graficoPressaoAtual",
        `${numero(dados.pressao)} hPa`
    );

    texto(
        "graficoLuminosidadeAtual",
        `${numero(dados.luminosidade)} lux`
    );

    texto(
        "graficoChuvaAtual",
        chovendo ? "1 mm" : "0 mm"
    );

    texto(
        "graficoQualidadeArAtual",
        `${numero(valorGas)}`
    );

    atualizarGauge("gaugeTemperatura", dados.temperatura);
    atualizarGauge("gaugeUmidade", dados.umidade);
    atualizarGauge("gaugeQualidadeAr", valorGas);

    atualizarLocalizacao(dados);
    atualizarCondicoesIdeais(dados);
    atualizarSensores(dados);
    atualizarPopupMapa();

    const data =
        dados.data_hora ||
        dados.data ||
        dados.timestamp ||
        dados.created_at;

    texto("ultimaAtualizacao", formatarDataHora(data));
    texto("atualizacaoCondicoes", formatarHora(data));
}

function atualizarGauge(id, valor) {
    const elemento = pegarElemento(id);
    const numeroValor = Number(valor);

    if (!elemento || !Number.isFinite(numeroValor)) {
        return;
    }

    elemento.setAttribute("aria-valuenow", numeroValor);
}

/*localização*/

function atualizarLocalizacao(dados) {
    const local =
        dados.localizacao ||
        dados.local ||
        "Estação meteorológica";

    const latitude = dados.latitude;
    const longitude = dados.longitude;

    texto("localizacaoEstacao", local);
    texto("localizacaoMapa", local);

    if (
        Number.isFinite(Number(latitude)) &&
        Number.isFinite(Number(longitude))
    ) {
        const lat = Number(latitude);
        const lon = Number(longitude);

        texto(
            "coordenadasEstacao",
            `${lat.toFixed(5)}, ${lon.toFixed(5)}`
        );

        texto(
            "latitudeEstacao",
            lat.toFixed(5)
        );

        texto(
            "longitudeEstacao",
            lon.toFixed(5)
        );

        atualizarMapa(lat, lon);
    }
}

/*condições ideais*/

function atualizarCondicoesIdeais(dados) {
    const temperatura = Number(dados.temperatura);
    const umidade = Number(dados.umidade);

    let titulo = "Condições favoráveis";
    let mensagem =
        "As condições atuais estão dentro de uma faixa confortável.";

    if (temperatura >= 35 && umidade < 30) {
        titulo = "Calor e baixa umidade";
        mensagem =
            "Temperatura elevada combinada com baixa umidade.";
    } else if (temperatura >= 35) {
        titulo = "Temperatura elevada";
        mensagem =
            "A temperatura está acima da faixa considerada ideal.";
    } else if (umidade < 30) {
        titulo = "Baixa umidade";
        mensagem =
            "A umidade está abaixo da faixa considerada ideal.";
    } else if (temperatura < 15) {
        titulo = "Temperatura baixa";
        mensagem =
            "A temperatura está abaixo da faixa considerada ideal.";
    }

    texto("condicaoIdealTitulo", titulo);
    texto("condicaoIdealMensagem", mensagem);
}

/*sensores*/

function atualizarSensores(dados) {
    const tempValida = Number.isFinite(Number(dados.temperatura)) && Number.isFinite(Number(dados.umidade));
    const pressaoValida = Number.isFinite(Number(dados.pressao)) && Number(dados.pressao) !== 1013.25;
    const ldrValido = Number.isFinite(Number(dados.luminosidade));
    const chuvaValida = dados.chuva !== null && dados.chuva !== undefined;
    const gasValido = Number.isFinite(Number(dados.qualidadeAr !== undefined ? dados.qualidadeAr : dados.qualidade_ar));

    atualizarStatusSensor("statusDHT22", tempValida);
    atualizarStatusSensor("statusBMP280", pressaoValida);
    atualizarStatusSensor("statusLDR", ldrValido);
    atualizarStatusSensor("statusChuva", chuvaValida);
    atualizarStatusSensor("statusGases", gasValido);
}

/*alertas*/

function criarAlerta(id, titulo, mensagem, tipo = "Atenção") {
    alertas.push({
        id: id,
        titulo: titulo,
        mensagem: mensagem,
        tipo: tipo,
        hora: new Date()
    });
}

function verificarAlertas() {
    alertas = [];

    if (!dadosAtuais) {
        return;
    }

    const temperatura = Number(dadosAtuais.temperatura);
    const umidade = Number(dadosAtuais.umidade);
    const pressao = Number(dadosAtuais.pressao);
    const qualidadeAr = Number(dadosAtuais.qualidadeAr);

    /*qualidade do ar*/

    if (
        Number.isFinite(qualidadeAr) &&
        qualidadeAr > REGRAS_ALERTAS.qualidadeAr.limite
    ) {
        criarAlerta(
            "ar",
            "Qualidade do ar",
            "A qualidade do ar está acima do limite definido.",
            "Atenção"
        );
    }

    /*calor seco*/

    if (
        temperatura >= REGRAS_ALERTAS.calorSeco.temperatura &&
        umidade < REGRAS_ALERTAS.calorSeco.umidade
    ) {
        criarAlerta(
            "calorSeco",
            "Calor seco",
            "Temperatura elevada combinada com baixa umidade.",
            "Alerta"
        );
    }

    /*queda de pressão*/

    if (historico.length >= 2) {
        const anterior =
            Number(historico[historico.length - 2]?.pressao);

        if (
            Number.isFinite(anterior) &&
            Number.isFinite(pressao) &&
            anterior - pressao >= REGRAS_ALERTAS.quedaPressao.limite
        ) {
            criarAlerta(
                "pressao",
                "Queda de pressão",
                "Foi identificada uma queda significativa na pressão atmosférica.",
                "Atenção"
            );
        }
    }

    /*onda de calor*/

    const ultimasTemperaturas = historico
        .slice(-REGRAS_ALERTAS.ondaCalor.leituras)
        .map(item => Number(item.temperatura))
        .filter(Number.isFinite);

    if (
        ultimasTemperaturas.length >=
        REGRAS_ALERTAS.ondaCalor.leituras &&
        ultimasTemperaturas.every(
            valor =>
                valor >= REGRAS_ALERTAS.ondaCalor.temperatura
        )
    ) {
        criarAlerta(
            "ondaCalor",
            "Onda de calor",
            "As últimas leituras apresentam temperaturas elevadas.",
            "Alerta"
        );
    }

    /*seca*/

    const ultimasChuvas = historico
        .slice(-REGRAS_ALERTAS.seca.leituras)
        .map(item => Number(item.chuva))
        .filter(Number.isFinite);

    if (
        ultimasChuvas.length >=
        REGRAS_ALERTAS.seca.leituras &&
        ultimasChuvas.every(
            valor =>
                valor <= REGRAS_ALERTAS.seca.chuvaMaxima
        )
    ) {
        criarAlerta(
            "seca",
            "Possível período de seca",
            "As últimas leituras apresentam baixo volume de chuva.",
            "Atenção"
        );
    }

    atualizarAlertas();
}

function atualizarAlertas() {
    const quantidade = alertas.length;

    texto("quantidadeAlertas", quantidade);

    const primeiro = alertas[0];

    if (primeiro) {
        mostrar("bannerAlertas", true);
        texto("tituloBannerAlerta", primeiro.titulo);
        texto("mensagemBannerAlerta", primeiro.mensagem);
        texto("tipoBannerAlerta", primeiro.tipo);
    } else {
        mostrar("bannerAlertas", false);
    }

    const ids = [
        "pressao",
        "ar",
        "calorSeco",
        "ondaCalor",
        "seca"
    ];

    ids.forEach(id => {
        const alerta = alertas.find(
            item => item.id === id
        );

        const nome =
            id.charAt(0).toUpperCase() + id.slice(1);

        mostrar(`alerta${nome}`, !!alerta);

        if (!alerta) {
            return;
        }

        texto(
            `tituloAlerta${nome}`,
            alerta.titulo
        );

        texto(
            `mensagemAlerta${nome}`,
            alerta.mensagem
        );

        texto(
            `horaAlerta${nome}`,
            formatarHora(alerta.hora)
        );
    });
}

/*resumo do período*/

function atualizarResumoPeriodo() {
    if (!historico.length) {
        return;
    }

    const temperaturas = historico
        .map(item => Number(item.temperatura))
        .filter(Number.isFinite);

    const umidades = historico
        .map(item => Number(item.umidade))
        .filter(Number.isFinite);

    const pressoes = historico
        .map(item => Number(item.pressao))
        .filter(Number.isFinite);

    const chuvas = historico
        .map(item => Number(item.chuva))
        .filter(Number.isFinite);

    const luminosidades = historico
        .map(item => Number(item.luminosidade))
        .filter(Number.isFinite);

    if (temperaturas.length) {
        texto(
            "temperaturaMaxima",
            `${Math.max(...temperaturas).toFixed(1)} °C`
        );

        texto(
            "temperaturaMinima",
            `${Math.min(...temperaturas).toFixed(1)} °C`
        );
    }

    if (umidades.length) {
        const media =
            umidades.reduce((a, b) => a + b, 0) /
            umidades.length;

        texto(
            "umidadeMedia",
            `${media.toFixed(1)} %`
        );
    }

    if (pressoes.length) {
        const media =
            pressoes.reduce((a, b) => a + b, 0) /
            pressoes.length;

        texto(
            "pressaoMedia",
            `${media.toFixed(1)} hPa`
        );
    }

    if (chuvas.length) {
        const total =
            chuvas.reduce((a, b) => a + b, 0);

        texto(
            "chuvaAcumulada",
            `${total.toFixed(1)} mm`
        );
    }

    if (luminosidades.length) {
        const media =
            luminosidades.reduce((a, b) => a + b, 0) /
            luminosidades.length;

        texto(
            "luminosidadeMedia",
            `${media.toFixed(1)} lux`
        );
    }
}

/*gráficos*/

function criarGrafico(chave, id, tipo, label, labels, valores) {
    const canvas = pegarElemento(id);

    if (!canvas) {
        return;
    }

    // Oculta o texto de fallback caso o gráfico seja renderizado
    const container = canvas.parentElement;
    if (container) {
        const fallback = container.querySelector(".grafico_fallback");
        if (fallback) {
            fallback.style.display = "none";
        }
    }

    const ctx = canvas.getContext("2d");

    if (graficos[chave]) {
        graficos[chave].data.labels = labels;
        graficos[chave].data.datasets[0].data = valores;
        graficos[chave].data.datasets[0].pointRadius = 0;
        graficos[chave].update();
        return;
    }

    graficos[chave] = new Chart(ctx, {
        type: tipo,

        data: {
            labels: labels,

            datasets: [{
                label: label,
                data: valores,
                borderWidth: 2,
                tension: 0.35,
                fill: tipo === "line",
                pointRadius: 0,
                pointHoverRadius: 5,
                pointHitRadius: 10
            }]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,

            elements: {
                point: {
                    radius: 0,
                    hoverRadius: 5,
                    hitRadius: 10
                }
            },

            plugins: {
                legend: {
                    display: false
                }
            },

            scales: {
                x: {
                    ticks: {
                        color: getCorTexto()
                    },

                    grid: {
                        color: getCorGrade()
                    }
                },

                y: {
                    ticks: {
                        color: getCorTexto()
                    },

                    grid: {
                        color: getCorGrade()
                    }
                }
            }
        }
    });

    atualizarCoresGrafico(graficos[chave]);
}

function atualizarGraficos() {
    if (!historico.length) {
        return;
    }

    const labels = historico.map(item => {
        const data =
            item.data ||
            item.timestamp ||
            item.created_at;

        return formatarHora(data);
    });

    criarGrafico(
        "temperatura",
        "graficoTemperatura",
        "line",
        "Temperatura",
        labels,
        historico.map(item => Number(item.temperatura))
    );

    criarGrafico(
        "umidade",
        "graficoUmidade",
        "line",
        "Umidade",
        labels,
        historico.map(item => Number(item.umidade))
    );

    criarGrafico(
        "pressao",
        "graficoPressao",
        "line",
        "Pressão",
        labels,
        historico.map(item => Number(item.pressao))
    );

    criarGrafico(
        "chuva",
        "graficoChuva",
        "line",
        "Chuva",
        labels,
        historico.map(item => Number(item.chuva))
    );
}

function getCorTexto() {
    const estilo = getComputedStyle(document.body);

    return estilo.getPropertyValue(
        "--cor-texto-secundario"
    ).trim() || "#64748b";
}

function getCorGrade() {
    const estilo = getComputedStyle(document.body);

    return estilo.getPropertyValue(
        "--cor-borda"
    ).trim() || "#e2e8f0";
}

function getCorGrafico() {
    const estilo = getComputedStyle(document.body);

    return estilo.getPropertyValue(
        "--cor-grafico"
    ).trim() || "#2563eb";
}

function getCorGraficoFundo() {
    const estilo = getComputedStyle(document.body);

    return estilo.getPropertyValue(
        "--cor-grafico-fundo"
    ).trim() || "rgba(37, 99, 235, 0.15)";
}

function atualizarCoresGrafico(grafico) {
    if (!grafico) {
        return;
    }

    const cor = getCorGrafico();
    const fundo = getCorGraficoFundo();
    const dataset = grafico.data.datasets[0];

    dataset.borderColor = cor;
    dataset.backgroundColor = fundo;
    dataset.pointBackgroundColor = cor;
    dataset.pointRadius = 0;
    dataset.pointHoverRadius = 5;

    grafico.options.scales.x.ticks.color = getCorTexto();
    grafico.options.scales.y.ticks.color = getCorTexto();

    grafico.options.scales.x.grid.color = getCorGrade();
    grafico.options.scales.y.grid.color = getCorGrade();

    grafico.update("none");
}

function atualizarCoresGraficos() {
    Object.values(graficos).forEach(
        atualizarCoresGrafico
    );
}

/*acessibilidade*/

function gerarResumoAcessibilidade() {
    if (!dadosAtuais) {
        return;
    }

    const temperatura = numero(dadosAtuais.temperatura);
    const umidade = numero(dadosAtuais.umidade);
    const pressao = numero(dadosAtuais.pressao);
    const qualidadeAr = numero(dadosAtuais.qualidadeAr);

    const resumo =
        `Temperatura ${temperatura} graus Celsius. ` +
        `Umidade ${umidade} por cento. ` +
        `Pressão ${pressao} hectopascais. ` +
        `Qualidade do ar ${qualidadeAr}. ` +
        `Existem ${alertas.length} alertas ativos.`;

    texto("resumoAcessibilidade", resumo);
}

function ouvirDados() {
    const elemento = pegarElemento("resumoAcessibilidade");

    if (!elemento) {
        return;
    }

    const resumo = elemento.textContent;

    if (!resumo || !("speechSynthesis" in window)) {
        return;
    }

    window.speechSynthesis.cancel();

    const fala = new SpeechSynthesisUtterance(resumo);

    fala.lang = "pt-BR";

    window.speechSynthesis.speak(fala);
}

const botaoOuvir = pegarElemento("ouvirDados");

if (botaoOuvir) {
    botaoOuvir.addEventListener("click", ouvirDados);
}

/*histórico*/

async function buscarHistorico() {
    try {
        const resposta = await buscarJSON(
            `${API_URL}/historico`
        );

        if (Array.isArray(resposta)) {
            historico = resposta;
        } else {
            historico =
                resposta.historico ||
                resposta.dados ||
                resposta.leituras ||
                [];
        }

        atualizarResumoPeriodo();
        atualizarGraficos();
        verificarAlertas();
        gerarResumoAcessibilidade();
        atualizarTabelaHistorico();

    } catch (erro) {
        console.error(
            "Erro ao buscar histórico:",
            erro
        );
    }
}

function atualizarTabelaHistorico() {
    const tbody = pegarElemento("ultimasLeituras");
    if (!tbody || !historico || !historico.length) {
        return;
    }

    const ultimas = historico.slice(-10).reverse();
    tbody.innerHTML = ultimas.map(item => {
        const data = item.data_hora || item.data || item.timestamp || item.created_at;
        const chovendo = Number(item.chuva) > 0 || item.chuva === true;
        const valorGas = item.qualidadeAr !== undefined ? item.qualidadeAr : item.qualidade_ar;
        return `
            <tr>
                <td>${formatarDataHora(data)}</td>
                <td><strong>${numero(item.temperatura)} °C</strong></td>
                <td>${numero(item.umidade)} %</td>
                <td>${numero(item.pressao)} hPa</td>
                <td>${numero(valorGas)}</td>
                <td>${chovendo ? '🌧️ Sim' : '☀️ Não'}</td>
            </tr>
        `;
    }).join("");
}

/*dados atuais — API*/

async function buscarDadosAtuais() {
    try {
        const dados = await buscarJSON(
            `${API_URL}/dados`
        );

        atualizarStatusEstacao(true);
        atualizarDadosAtuais(dados);

    } catch (erro) {
        console.error(
            "Erro ao buscar dados atuais:",
            erro
        );

        atualizarStatusEstacao(false);
        texto(
            "ultimaAtualizacao",
            "Não foi possível atualizar"
        );
    }
}

/*atualização geral*/

async function atualizarTudo() {
    await buscarDadosAtuais();
    await buscarHistorico();
}

/*inicialização*/

function iniciar() {
    atualizarTema();

    /*
     * Primeiro cria o mapa.
     * Depois busca os dados da API.
     */

    inicializarMapa();
    atualizarTudo();

    setInterval(
        atualizarTudo,
        5000
    );
}

document.addEventListener(
    "DOMContentLoaded",
    iniciar
);